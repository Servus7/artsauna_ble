# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Artsauna-BLE - integration for Home Assistant
# Copyright (C) 2025 David & Philipp Aderbauer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Artsauna BLE integration number platform."""

import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from propcache.api import cached_property

from .artsauna_ble import ArtsaunaBLEAdapter
from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_ARTSAUNA, DEVICE_TYPE_KDY, DOMAIN
from .coordinator import ArtsaunaBLECoordinator
from .kdy_ble import KdyBLEAdapter
from .models import ArtsaunaBLEData

_LOGGER = logging.getLogger(__name__)

VOLUME_DESCRIPTION = NumberEntityDescription(
    key="volume",
    translation_key="volume",
    entity_category=EntityCategory.CONFIG,
    device_class=NumberDeviceClass.SOUND_PRESSURE,
    mode=NumberMode.SLIDER,
    native_min_value=0,
    native_max_value=40,
    native_step=1,
)
KDY_VOLUME_DESCRIPTION = NumberEntityDescription(
    key="volume",
    translation_key="volume",
    entity_category=EntityCategory.CONFIG,
    device_class=NumberDeviceClass.SOUND_PRESSURE,
    mode=NumberMode.SLIDER,
    native_min_value=1,
    native_max_value=20,
    native_step=1,
)
# EXPERIMENTAL — stepper concept, only wired up on this test branch.
# There is no absolute-set command for these (PROTOCOL.md); the entity
# fakes it by repeating relative up/down commands (see
# KdyBLEAdapter._step_to_target). Not yet verified against real hardware.
KDY_TARGET_TEMP_DESCRIPTION = NumberEntityDescription(
    key="target_temp",
    translation_key="target_temp",
    icon="mdi:thermometer",
    mode=NumberMode.BOX,
    native_min_value=0,
    native_max_value=250,
    native_step=1,
)
KDY_TIMER_DESCRIPTION = NumberEntityDescription(
    key="timer",
    translation_key="remaining_time",
    icon="mdi:timer-outline",
    mode=NumberMode.BOX,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    native_min_value=0,
    native_max_value=180,
    native_step=1,
)

SENSOR_DESCRIPTIONS = [
    VOLUME_DESCRIPTION,
]

KDY_SENSOR_DESCRIPTIONS = [
    KDY_VOLUME_DESCRIPTION,
    KDY_TARGET_TEMP_DESCRIPTION,
    KDY_TIMER_DESCRIPTION,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform for ArtsaunaBLE."""
    data: ArtsaunaBLEData = hass.data[DOMAIN][entry.entry_id]

    if entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_ARTSAUNA) == DEVICE_TYPE_KDY:
        assert isinstance(data.device, KdyBLEAdapter)
        async_add_entities(
            KdyBLENumber(
                data.coordinator,
                data.device,
                entry.title,
                description,
            )
            for description in KDY_SENSOR_DESCRIPTIONS
        )
        return

    assert isinstance(data.device, ArtsaunaBLEAdapter)
    async_add_entities(
        ArtsaunaBLENumber(
            data.coordinator,
            data.device,
            entry.title,
            description,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class ArtsaunaBLENumber(CoordinatorEntity[ArtsaunaBLECoordinator], NumberEntity):
    """Generic sensor for ArtsaunaBLE."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True
    _attr_entity_registry_visible_default = True

    def __init__(
        self,
        coordinator: ArtsaunaBLECoordinator,
        device: ArtsaunaBLEAdapter,
        name: str,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device = device
        self.entity_description = description
        self._key = description.key
        self._attr_unique_id = f"{device.address}_{self._key}"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(device_registry.CONNECTION_BLUETOOTH, device.address)},
            manufacturer="HiMaterial",
            model="Artsauna",
        )
        self._attr_native_value = 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        match self._key:
            case "volume":
                self._attr_native_value = self._device.volume
            case _:
                _LOGGER.error("Wrong KEY for number: %s", self._key)
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        match self._key:
            case "volume":
                await self._device.send_set_volume(int(value) % 50)
            case _:
                _LOGGER.error("Wrong KEY for number: %s", self._key)

    @property
    def available(self) -> bool:
        return super().available and self._device.is_power_on

    @cached_property
    def icon(self) -> str | None:
        match self._key:
            case "volume":
                if not self._attr_native_value:
                    return "mdi:volume-off"
                if self._attr_native_value <= 16:
                    return "mdi:volume-low"
                if self._attr_native_value <= 33:
                    return "mdi:volume-medium"
                if self._attr_native_value <= 50:
                    return "mdi:volume-high"
        return super().icon


class KdyBLENumber(CoordinatorEntity[ArtsaunaBLECoordinator], NumberEntity):
    """Number for KDY Sauna BLE devices."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True
    _attr_entity_registry_visible_default = True

    def __init__(
        self,
        coordinator: ArtsaunaBLECoordinator,
        device: KdyBLEAdapter,
        name: str,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device = device
        self.entity_description = description
        self._key = description.key
        self._attr_unique_id = f"{device.address}_{self._key}"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(device_registry.CONNECTION_BLUETOOTH, device.address)},
            manufacturer="KDY",
            model="KDYSauna",
        )
        self._attr_native_value = 1

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        match self._key:
            case "volume":
                self._attr_native_value = self._device.volume
            case "target_temp":
                self._attr_native_value = self._device.target_temp
                self._sensor_option_unit_of_measurement = (
                    UnitOfTemperature.CELSIUS
                    if self._device.is_unit_celsius
                    else UnitOfTemperature.FAHRENHEIT
                )
            case "timer":
                self._attr_native_value = self._device.remaining_time
            case _:
                _LOGGER.error("Wrong KEY for KDY number: %s", self._key)
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value.

        EXPERIMENTAL for target_temp/timer: no absolute-set command exists,
        so this fakes it via repeated relative step commands — see
        KdyBLEAdapter._step_to_target.
        """
        match self._key:
            case "volume":
                await self._device.send_set_volume(int(value))
            case "target_temp":
                await self._device.send_set_target_temp(int(value))
            case "timer":
                await self._device.send_set_timer(int(value))
            case _:
                _LOGGER.error("Wrong KEY for KDY number: %s", self._key)

    @property
    def available(self) -> bool:
        return super().available and self._device.is_power_on

    @cached_property
    def native_unit_of_measurement(self) -> str | None:
        if self._key == "target_temp":
            return (
                UnitOfTemperature.CELSIUS
                if self._device.is_unit_celsius
                else UnitOfTemperature.FAHRENHEIT
            )
        return super().native_unit_of_measurement

    @cached_property
    def icon(self) -> str | None:
        match self._key:
            case "volume":
                if not self._attr_native_value:
                    return "mdi:volume-off"
                if self._attr_native_value <= 7:
                    return "mdi:volume-low"
                if self._attr_native_value <= 14:
                    return "mdi:volume-medium"
                return "mdi:volume-high"
        return super().icon
