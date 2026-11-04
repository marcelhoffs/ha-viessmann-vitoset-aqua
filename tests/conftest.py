"""Shared fixtures for the Viessmann Vitoset Aqua tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

from PyViCare.PyViCareCachedService import ViCareCachedService
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareService import ViCareDeviceAccessor
from PyViCare.PyViCareWaterTreatment import WaterTreatment
import pytest

from custom_components.viessmann_vitoset.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

# Features of a real VitosetAqua87S, with identifiers stripped. Its leak slots
# are empty: `paired_leak_sensor` fills slot 0 in the shape PyViCare expects.
FIXTURE = json.loads((Path(__file__).parent / "fixtures/softener.json").read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components/ discoverable to Home Assistant during tests."""
    yield


@pytest.fixture
def features() -> dict:
    """Return the feature payload the fake API serves, for tests to change."""
    return copy.deepcopy(FIXTURE)


@pytest.fixture
def paired_leak_sensor(features: dict) -> None:
    """Pair a leak sensor to slot 0, currently detecting no leak."""
    values = {
        "water.leakDetection.sensors.leakage.0": {
            "value": {"value": False},
            "status": {"value": "connected"},
        },
        "water.leakDetection.sensors.leakage.0.battery": {"level": {"value": 90}},
        "water.leakDetection.sensors.leakage.0.rssi": {"value": {"value": -60}},
    }
    for feature in features["data"]:
        if feature["feature"] in values:
            feature["isEnabled"] = True
            feature["properties"] = values[feature["feature"]]


class FakeOAuth:
    """Serve the features through PyViCare's real cache and parsing code."""

    def __init__(self, features: dict) -> None:
        self.features = features
        self.gets = 0

    def get(self, url: str) -> dict:
        self.gets += 1
        return self.features


@pytest.fixture
def api(features: dict) -> FakeOAuth:
    """Return the fake API."""
    return FakeOAuth(features)


@pytest.fixture
def softener(api: FakeOAuth) -> WaterTreatment:
    """Return a real WaterTreatment reading from the fake API."""
    service = ViCareCachedService(api, [], 60)
    accessor = ViCareDeviceAccessor(1, "SERIAL", "0")
    return WaterTreatment(accessor, service, [])


@pytest.fixture
def mock_vicare(softener: WaterTreatment):
    """Make the integration find `softener` next to an unrelated heat pump."""
    heatpump = PyViCareDeviceConfig(
        softener.accessor, softener.service, "E3_Vitocal_11", "Online", "heating"
    )
    device = PyViCareDeviceConfig(
        softener.accessor,
        softener.service,
        "E3_VitosetAqua_1121",
        "Online",
        "WaterSoftener",
    )
    with patch("custom_components.viessmann_vitoset.PyViCare") as vicare:
        vicare.return_value.all_devices = [heatpump, device]
        yield vicare
