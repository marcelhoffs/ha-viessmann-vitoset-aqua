"""Tests for setup, polling and reauth of the Viessmann Vitoset Aqua integration."""
from __future__ import annotations

from datetime import timedelta
import time
from unittest.mock import patch

from PyViCare.PyViCareUtils import (
    PyViCareInvalidCredentialsError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
from PyViCare.PyViCareWaterTreatment import WaterTreatment
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.viessmann_vitoset.const import DOMAIN, SCAN_INTERVAL
from custom_components.viessmann_vitoset.coordinator import read_values


def _feature(features: dict, name: str) -> dict:
    return next(f for f in features["data"] if f["feature"] == name)


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "token",
                "refresh_token": "refresh",
                "expires_at": time.time() + 3600,
            },
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.viessmann_vitoset.async_get_config_entry_implementation"
    ):
        await async_setup_component(hass, "application_credentials", {})
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, platform: str, key: str):
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"SERIAL_{key}"
    )
    return hass.states.get(entity_id)


def test_read_values_parses_a_real_payload(softener: WaterTreatment) -> None:
    assert read_values(softener) == {
        "model": "VitosetAqua87S",
        "salt_days_remaining": 181,
        "low_salt_alert_days": 14,
        "water_total": 10508,
        "water_today": 117,
        "water_last_seven_days": 125,
        "flow_current": 0.0,
        "flow_max": 11.9,
        "valve_position": "transition",
        "valve_motor": "off",
        "holiday_mode": False,
    }


def test_read_values_tolerates_a_missing_feature(
    softener: WaterTreatment, features: dict
) -> None:
    features["data"].remove(_feature(features, "water.consumption.summary"))
    values = read_values(softener)
    assert values["water_today"] is None
    assert values["salt_days_remaining"] == 181


async def test_setup_creates_entities(hass: HomeAssistant, mock_vicare) -> None:
    entry = await _setup(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert _state(hass, SENSOR_DOMAIN, "salt_days_remaining").state == "181"
    assert _state(hass, SENSOR_DOMAIN, "water_total").attributes["device_class"] == "water"
    assert _state(hass, SENSOR_DOMAIN, "valve_position").state == "transition"
    assert _state(hass, BINARY_SENSOR_DOMAIN, "holiday_mode").state == STATE_OFF
    assert not er.async_get(hass).async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, "SERIAL_leak_0"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("paired_leak_sensor")
async def test_leak_sensor_entities(hass: HomeAssistant, mock_vicare) -> None:
    await _setup(hass)

    leak = _state(hass, BINARY_SENSOR_DOMAIN, "leak_0")
    assert leak.state == STATE_OFF
    assert leak.attributes["device_class"] == "moisture"
    assert leak.name == "Vitoset Aqua Leak sensor 1"
    assert _state(hass, SENSOR_DOMAIN, "leak_0_battery").state == "90"
    # Signal strength is off by default.
    assert _state(hass, SENSOR_DOMAIN, "leak_0_rssi") is None


@pytest.mark.usefixtures("paired_leak_sensor")
async def test_leak_state_tracks_api_and_unreadable_is_not_off(
    hass: HomeAssistant, mock_vicare, features: dict
) -> None:
    await _setup(hass)
    leak = _feature(features, "water.leakDetection.sensors.leakage.0")

    leak["properties"]["value"]["value"] = True
    async_fire_time_changed(hass, _next_poll())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, BINARY_SENSOR_DOMAIN, "leak_0").state == STATE_ON

    del leak["properties"]["value"]
    async_fire_time_changed(hass, _next_poll(2))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, BINARY_SENSOR_DOMAIN, "leak_0").state == STATE_UNKNOWN


def _next_poll(polls: int = 1):
    return dt_util.utcnow() + SCAN_INTERVAL * polls + timedelta(seconds=1)


async def test_each_poll_costs_one_api_call_and_is_never_stale(
    hass: HomeAssistant, mock_vicare, api, features: dict
) -> None:
    await _setup(hass)
    gets = api.gets

    _feature(features, "water.softener.salt.level.days")["properties"]["remaining"][
        "value"
    ] = 180
    async_fire_time_changed(hass, _next_poll())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert api.gets == gets + 1
    assert _state(hass, SENSOR_DOMAIN, "salt_days_remaining").state == "180"


async def test_no_softener_on_account_fails_setup(
    hass: HomeAssistant, mock_vicare
) -> None:
    mock_vicare.return_value.all_devices = mock_vicare.return_value.all_devices[:1]
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "error",
    [
        PyViCareRateLimitError(
            {"extendedPayload": {"name": "x", "requestCountLimit": 1, "limitReset": 0}}
        ),
        PyViCareNotSupportedFeatureError("PACKAGE_NOT_PAID_FOR"),
    ],
)
async def test_api_error_during_setup_retries(
    hass: HomeAssistant, mock_vicare, error: Exception
) -> None:
    mock_vicare.return_value.initWithExternalOAuth.side_effect = error
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_api_error_makes_entities_unavailable(
    hass: HomeAssistant, mock_vicare, api
) -> None:
    await _setup(hass)

    with patch.object(api, "get", side_effect=PyViCareRateLimitError(
        {"extendedPayload": {"name": "x", "requestCountLimit": 1, "limitReset": 0}}
    )):
        async_fire_time_changed(hass, _next_poll())
        await hass.async_block_till_done(wait_background_tasks=True)

    assert _state(hass, SENSOR_DOMAIN, "salt_days_remaining").state == STATE_UNAVAILABLE


async def test_rejected_credentials_start_reauth(
    hass: HomeAssistant, mock_vicare, api
) -> None:
    entry = await _setup(hass)

    with patch.object(api, "get", side_effect=PyViCareInvalidCredentialsError()):
        async_fire_time_changed(hass, _next_poll())
        await hass.async_block_till_done(wait_background_tasks=True)

    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    )
