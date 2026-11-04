"""Data update coordinator for the Viessmann Vitoset Aqua integration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC
import logging
from typing import Any

from PyViCare.PyViCareUtils import (
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
from PyViCare.PyViCareWaterTreatment import WaterTreatment

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import API_ERRORS, HomeAssistantAuth
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

MAX_RATE_LIMIT_WAIT = 24 * 60 * 60

type VitosetConfigEntry = ConfigEntry[VitosetCoordinator]


def _safe(read: Callable[[], Any]) -> Any:
    """Return a value, or None when it's missing or malformed.

    One unreadable value must not take every other entity down with it.
    """
    try:
        return read()
    except (KeyError, TypeError, ValueError, PyViCareNotSupportedFeatureError):
        return None


def read_values(softener: WaterTreatment) -> dict[str, Any]:
    """Read every value from PyViCare's feature cache, without further API calls."""

    def summary(period: str) -> Any:
        return softener.getProperty("water.consumption.summary")["properties"][period][
            "value"
        ]

    values = {
        "model": _safe(
            lambda: softener.getProperty("device.variant")["properties"]["value"]["value"]
        ),
        "salt_days_remaining": _safe(softener.getSaltDaysRemaining),
        "low_salt_alert_days": _safe(softener.getLowSaltAlertDays),
        "water_total": _safe(softener.getTotalConsumption),
        "water_today": _safe(lambda: summary("currentDay")),
        "water_last_seven_days": _safe(lambda: summary("lastSevenDays")),
        "flow_current": _safe(softener.getCurrentFlow),
        "flow_max": _safe(softener.getMaxFlow),
        "valve_position": _safe(softener.getShutoffPosition),
        "valve_motor": _safe(softener.getShutoffMotorState),
        "holiday_mode": _safe(softener.getHolidayModeActive),
    }
    leaks = softener.leakSensors
    values["leak_slots"] = [leak.id for leak in leaks]
    for leak in leaks:
        # A disconnected sensor can't vouch for "no leak", so leave it unknown.
        connected = _safe(leak.getStatus) == "connected"
        values[f"leak_{leak.id}"] = _safe(leak.getLeakDetected) if connected else None
        values[f"leak_{leak.id}_battery"] = _safe(leak.getBatteryPercent)
        values[f"leak_{leak.id}_rssi"] = _safe(leak.getRssi)
    return values


class VitosetCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the softener's features from the ViCare API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VitosetConfigEntry,
        softener: WaterTreatment,
        auth: HomeAssistantAuth,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.softener = softener
        self._auth = auth

    def _fetch(self) -> dict[str, Any]:
        # Clearing first makes a failed fetch raise, instead of PyViCare
        # silently serving the previous poll's values as fresh.
        self.softener.service.clear_cache()
        try:
            self.softener.service.fetch_all_features(self.softener.accessor)
        except PyViCareRateLimitError as err:
            # limitResetDate is naive UTC and can be in the past.
            reset = err.limitResetDate.replace(tzinfo=UTC)
            wait = (reset - dt_util.utcnow()).total_seconds()
            raise UpdateFailed(
                f"ViCare API rate limit reached: {err}",
                retry_after=min(
                    max(wait, SCAN_INTERVAL.total_seconds()), MAX_RATE_LIMIT_WAIT
                ),
            ) from err
        except API_ERRORS as err:
            raise UpdateFailed(f"Error communicating with ViCare: {err}") from err
        return read_values(self.softener)

    async def _async_update_data(self) -> dict[str, Any]:
        await self._auth.async_refresh()
        return await self.hass.async_add_executor_job(self._fetch)
