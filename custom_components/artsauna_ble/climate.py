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

"""Climate platform for Artsauna and KDY sauna BLE devices.

Exposes on/off, current/target temperature, and remaining time. Temperature
and timer are adjusted via the existing button entities (step-only BLE
commands) — no climate setpoint slider.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .artsauna_ble import ArtsaunaBLEAdapter
from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_ARTSAUNA, DEVICE_TYPE_KDY, DOMAIN
from .coordinator import ArtsaunaBLECoordinator
from .kdy_ble import KdyBLEAdapter
from .models import ArtsaunaBLEData

ATTR_REMAINING_TIME = "remaining_time"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    data: ArtsaunaBLEData = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_ARTSAUNA)

    if device_type == DEVICE_TYPE_KDY:
        assert isinstance(data.device, KdyBLEAdapter)
        async_add_entities(
            [KdyBLEClimate(data.coordinator, data.device, entry.title)]
        )
        return

    assert isinstance(data.device, ArtsaunaBLEAdapter)
    async_add_entities(
        [ArtsaunaBLEClimate(data.coordinator, data.device, entry.title)]
    )


class _SaunaClimateBase(CoordinatorEntity[ArtsaunaBLECoordinator], ClimateEntity):
    """Shared climate behaviour for step-only sauna protocols."""

    _attr_has_entity_name = True
    _attr_translation_key = "sauna"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 30
    _attr_max_temp = 110
    _attr_target_temperature_step = 1
    _attr_entity_registry_enabled_default = True
    _attr_entity_registry_visible_default = True

    def __init__(
        self,
        coordinator: ArtsaunaBLECoordinator,
        device: ArtsaunaBLEAdapter | KdyBLEAdapter,
        name: str,
        *,
        manufacturer: str,
        model: str,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device = device
        self._attr_unique_id = f"{device.address}_climate"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(device_registry.CONNECTION_BLUETOOTH, device.address)},
            manufacturer=manufacturer,
            model=model,
        )
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.OFF
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._remaining_time = 0

    @property
    def temperature_unit(self) -> str:
        if self._device.is_unit_celsius:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_REMAINING_TIME: self._remaining_time}

    @property
    def available(self) -> bool:
        return super().available and self._coordinator.connected

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.HEAT:
            await self._set_power(True)
            self._attr_hvac_mode = HVACMode.HEAT
        elif hvac_mode == HVACMode.OFF:
            await self._set_power(False)
            self._attr_hvac_mode = HVACMode.OFF
        else:
            return
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def _set_power(self, desired_on: bool) -> None:
        if self._device.is_power_on != desired_on:
            await self._device.send_toggle_power()

    def _apply_common_state(self) -> None:
        self._attr_current_temperature = float(self._device.current_temp)
        self._attr_target_temperature = float(self._device.target_temp)
        self._remaining_time = int(self._device.remaining_time)
        if self._device.is_power_on:
            self._attr_hvac_mode = HVACMode.HEAT
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF


class ArtsaunaBLEClimate(_SaunaClimateBase):
    """Climate entity for Artsauna BLE devices."""

    def __init__(
        self,
        coordinator: ArtsaunaBLECoordinator,
        device: ArtsaunaBLEAdapter,
        name: str,
    ) -> None:
        super().__init__(
            coordinator,
            device,
            name,
            manufacturer="HiMaterial",
            model="Artsauna",
        )
        self._device: ArtsaunaBLEAdapter

    @callback
    def _handle_coordinator_update(self) -> None:
        self._apply_common_state()
        if self._device.is_power_on:
            self._attr_hvac_action = (
                HVACAction.HEATING
                if self._device.is_heating_on
                else HVACAction.IDLE
            )
        self.async_write_ha_state()


class KdyBLEClimate(_SaunaClimateBase):
    """Climate entity for KDY Sauna BLE devices."""

    def __init__(
        self,
        coordinator: ArtsaunaBLECoordinator,
        device: KdyBLEAdapter,
        name: str,
    ) -> None:
        super().__init__(
            coordinator,
            device,
            name,
            manufacturer="KDY",
            model="KDYSauna",
        )
        self._device: KdyBLEAdapter

    @callback
    def _handle_coordinator_update(self) -> None:
        self._apply_common_state()
        if self._device.is_power_on:
            self._attr_hvac_action = HVACAction.HEATING
        self.async_write_ha_state()
