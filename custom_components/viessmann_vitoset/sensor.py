"""Sensor platform for the Viessmann Vitoset Aqua integration."""
from __future__ import annotations

import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VitosetConfigEntry
from .entity import VitosetEntity

SENSORS = (
    SensorEntityDescription(
        key="salt_days_remaining",
        translation_key="salt_days_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="low_salt_alert_days",
        translation_key="low_salt_alert_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # The one to use in the Energy dashboard; the others would double count.
    SensorEntityDescription(
        key="water_total",
        translation_key="water_total",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="water_today",
        translation_key="water_today",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Rolling window: it goes up and down, so no state class fits.
    SensorEntityDescription(
        key="water_last_seven_days",
        translation_key="water_last_seven_days",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="flow_current",
        translation_key="flow_current",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="flow_max",
        translation_key="flow_max",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(key="valve_position", translation_key="valve_position"),
    SensorEntityDescription(
        key="valve_motor",
        translation_key="valve_motor",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def leak_slots(data: dict[str, Any]) -> list[int]:
    """Return the slots with a paired leak sensor.

    shortcut: slots are read once at startup, so pairing a new sensor needs a
    reload of the integration. Add a coordinator listener if that gets annoying.
    """
    return [int(m[1]) for key in data if (m := re.fullmatch(r"leak_(\d+)", key))]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitosetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    entities = [VitosetSensor(coordinator, description) for description in SENSORS]
    for slot in leak_slots(coordinator.data):
        entities.append(
            VitosetSensor(
                coordinator,
                SensorEntityDescription(
                    key=f"leak_{slot}_battery",
                    translation_key="leak_battery",
                    device_class=SensorDeviceClass.BATTERY,
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
                slot,
            )
        )
        entities.append(
            VitosetSensor(
                coordinator,
                SensorEntityDescription(
                    key=f"leak_{slot}_rssi",
                    translation_key="leak_rssi",
                    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                ),
                slot,
            )
        )
    async_add_entities(entities)


class VitosetSensor(VitosetEntity, SensorEntity):
    """A numeric or text softener value."""

    @property
    def native_value(self) -> Any:
        return self._value
