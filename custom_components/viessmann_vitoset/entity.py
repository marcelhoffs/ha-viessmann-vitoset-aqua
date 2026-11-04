"""Shared entity base for the Viessmann Vitoset Aqua integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VitosetCoordinator


class VitosetEntity(CoordinatorEntity[VitosetCoordinator]):
    """One value from the coordinator, on the softener's device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VitosetCoordinator,
        description: EntityDescription,
        leak_slot: int | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        serial = coordinator.softener.accessor.serial
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name="Vitoset Aqua",
            manufacturer="Viessmann",
            model=coordinator.data["model"],
        )
        if leak_slot is not None:
            self._attr_translation_placeholders = {"slot": str(leak_slot + 1)}

    @property
    def _value(self):
        return self.coordinator.data.get(self.entity_description.key)
