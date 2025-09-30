"""Sensor platform for Minut HACS integration.

This module defines temperature, humidity and noise sensors for each Minut
device. Sensors are derived from the data provided by the coordinator.
"""

from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES
from .coordinator import MinutDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Minut sensors from a config entry."""
    coordinator: MinutDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = []
    # Create an entity for each device and sensor type
    for device_id, data in coordinator.data.items():
        device = data["device"]
        for sensor_key, info in SENSOR_TYPES.items():
            entities.append(MinutSensor(coordinator, device_id, device, sensor_key, info))
    async_add_entities(entities)


class MinutSensor(CoordinatorEntity[MinutDataUpdateCoordinator], SensorEntity):
    """Representation of a Minut sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinutDataUpdateCoordinator,
        device_id: str,
        device: dict[str, Any],
        sensor_key: str,
        sensor_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device = device
        self._sensor_key = sensor_key
        self._sensor_info = sensor_info
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        name_prefix = device.get("description") or device.get("name") or f"Point {device_id}"
        self._attr_name = f"{name_prefix} {sensor_info['name']}"
        # Set unit, device class, state class
        self._attr_unit_of_measurement = sensor_info["unit"]
        device_class = sensor_info.get("device_class")
        if device_class == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif device_class == "humidity":
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif device_class:
            # Generic or None; set as string to allow unknown types
            self._attr_device_class = SensorDeviceClass(device_class)
        self._attr_state_class = SensorStateClass.MEASUREMENT

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
    def native_value(self) -> Any:
        """Return the current sensor value."""
        data = self.coordinator.data.get(self._device_id)
        if not data:
            return None
        return data["sensors"].get(self._sensor_key)