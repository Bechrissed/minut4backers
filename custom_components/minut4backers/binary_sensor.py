"""Binary sensor platform for the Minut HACS integration.

This module defines binary sensors for motion and alarm detection. The
states of these sensors are derived from recent timeline events. When an
event matching one of the configured types occurs, the corresponding
binary sensor will be set to ``True`` for the duration of the polling
interval. When no recent events are found, the sensor resets to ``False``.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BINARY_SENSOR_EVENTS
from .coordinator import MinutDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Minut binary sensors from a config entry."""
    coordinator: MinutDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[BinarySensorEntity] = []
    for device_id, data in coordinator.data.items():
        device = data["device"]
        for binary_key, config in BINARY_SENSOR_EVENTS.items():
            entities.append(MinutBinarySensor(coordinator, device_id, device, binary_key, config))
    async_add_entities(entities)


class MinutBinarySensor(CoordinatorEntity[MinutDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a Minut binary sensor based on timeline events."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinutDataUpdateCoordinator,
        device_id: str,
        device: dict[str, Any],
        binary_key: str,
        config: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device = device
        self._binary_key = binary_key
        self._config = config
        self._attr_unique_id = f"{device_id}_{binary_key}"
        name_prefix = device.get("description") or device.get("name") or f"Point {device_id}"
        self._attr_name = f"{name_prefix} {binary_key.capitalize()}"
        # Map the device class string to the corresponding enum if available
        device_class = config.get("device_class")
        if device_class:
            try:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
            except ValueError:
                # Unknown device class; ignore
                pass

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information for registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            name=self._device.get("description") or self._device.get("name"),
            manufacturer="Minut",
            model=self._device.get("model") or "Point",
        )

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state based on recent events."""
        data = self.coordinator.data.get(self._device_id)
        if not data:
            return None
        return data["binary"].get(self._binary_key)