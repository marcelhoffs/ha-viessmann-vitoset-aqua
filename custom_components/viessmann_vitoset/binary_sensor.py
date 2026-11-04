"""Binary sensor platform for the Viessmann Vitoset Aqua integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VitosetConfigEntry
from .entity import VitosetEntity
from .sensor import leak_slots


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitosetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    entities = [
        VitosetBinarySensor(
            coordinator,
            BinarySensorEntityDescription(
                key="holiday_mode", translation_key="holiday_mode"
            ),
        )
    ]
    for slot in leak_slots(coordinator.data):
        entities.append(
            VitosetBinarySensor(
                coordinator,
                BinarySensorEntityDescription(
                    key=f"leak_{slot}",
                    translation_key="leak",
                    device_class=BinarySensorDeviceClass.MOISTURE,
                ),
                slot,
            )
        )
    async_add_entities(entities)


class VitosetBinarySensor(VitosetEntity, BinarySensorEntity):
    """A boolean softener value; None stays unknown rather than reading as off."""

    @property
    def is_on(self) -> bool | None:
        return self._value
