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

"""Single-connection KDY Sauna BLE adapter.

All status notifications and future commands must use this one Bleak client.
Phase 1: notify/read only — no write payloads.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from functools import cached_property

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakNotFoundError,
    establish_connection,
)
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CHARACTERISTIC_FFF1,
    CHARACTERISTIC_FFF2,
    short_uuid,
)
from .models import InvalidStatusPacket, KdyState

_LOGGER = logging.getLogger(__name__)
BLEAK_BACKOFF_TIME = 0.25


class KdyBLEAdapter:
    """KDY Sauna BLE adapter with a single shared connection."""

    def __init__(self, ble_device: BLEDevice) -> None:
        self._ble_device = ble_device
        self._advertisement_data: AdvertisementData | None = None
        self._state = KdyState()
        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        self._callbacks: list[Callable[[KdyState], None]] = []
        self._disconnected_callbacks: list[Callable[[], None]] = []
        self._expected_disconnect = False

    @cached_property
    def address(self) -> str:
        """Return the address."""
        return format_mac(self._ble_device.address)

    @cached_property
    def name(self) -> str:
        """Get the name of the device."""
        return self._ble_device.name or self.address

    @property
    def state(self) -> KdyState:
        return self._state

    @property
    def is_power_on(self) -> bool:
        return self._state.power

    @property
    def target_temp(self) -> int:
        return self._state.target_temp

    @property
    def current_temp(self) -> int:
        return self._state.current_temp

    @property
    def remaining_time(self) -> int:
        return self._state.remaining_minutes

    @property
    def is_unit_celsius(self) -> bool:
        # observed temps are °C as raw bytes; °F encoding is unknown
        return True

    async def initialise(self) -> None:
        """Connect and subscribe to notifications on the shared client."""
        await self._ensure_connected()

        if self._client is None:
            _LOGGER.debug("%s: Client is unexpectedly None", self.name)
            return

        _LOGGER.debug("%s: Subscribe to FFF2 status notifications", self.name)
        await self._client.start_notify(
            CHARACTERISTIC_FFF2, self._notification_handler
        )
        # FFF1 also has notify — log RAW only until meaning is verified
        try:
            await self._client.start_notify(
                CHARACTERISTIC_FFF1, self._notification_handler
            )
            _LOGGER.debug("%s: Also subscribed to FFF1 for RAW logging", self.name)
        except BleakError:
            _LOGGER.debug(
                "%s: FFF1 notify subscribe failed (optional)", self.name, exc_info=True
            )

    def set_ble_device_and_advertisement_data(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Set the ble device."""
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data

    def _notification_handler(self, characteristic: object, data: bytearray) -> None:
        """Handle notification responses on the single connection."""
        char_uuid = getattr(characteristic, "uuid", None)
        label = short_uuid(str(char_uuid)) if char_uuid else "UNKNOWN"
        raw_hex = bytes(data).hex()
        _LOGGER.debug("%s: RAW notification %s: %s", self.name, label, raw_hex)

        # Status frames are observed on FFF2; ignore non-status FFF1 noise for state
        uuid_str = str(char_uuid).lower() if char_uuid else ""
        if uuid_str and uuid_str != CHARACTERISTIC_FFF2.lower():
            return

        try:
            new_state = KdyState.from_ble_status(data)
        except InvalidStatusPacket:
            _LOGGER.debug(
                "%s: Non-status or invalid FFF2 payload (kept as RAW only): %s",
                self.name,
                raw_hex,
            )
            return

        self._state = new_state
        _LOGGER.debug(
            "%s: Decoded status: %s | RAW: %s",
            self.name,
            new_state.format_known_fields(),
            raw_hex,
        )
        self._fire_callbacks()

    async def _ensure_connected(self) -> None:
        """Ensure connection to device is established."""
        if self._connect_lock.locked():
            _LOGGER.debug(
                "%s: Connection already in progress, waiting for it to complete",
                self.name,
            )
        if self._client and self._client.is_connected:
            return
        async with self._connect_lock:
            if self._client and self._client.is_connected:
                return
            _LOGGER.debug("%s: Connecting", self.name)
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self.name,
                self._disconnected,
                use_services_cache=True,
                ble_device_callback=lambda: self._ble_device,
            )
            _LOGGER.debug("%s: Connected", self.name)
            self._client = client

    async def _reconnect(self) -> None:
        """Attempt a reconnect on the same adapter instance."""
        _LOGGER.debug("%s: ensuring connection", self.name)
        try:
            await self._ensure_connected()
            _LOGGER.debug("%s: ensured connection - initialising", self.name)
            await self.initialise()
        except BleakNotFoundError:
            _LOGGER.debug("%s: failed to ensure connection - backing off", self.name)
            await asyncio.sleep(BLEAK_BACKOFF_TIME)
            asyncio.create_task(self._reconnect())

    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Disconnected callback."""
        self._fire_disconnected_callbacks()
        if self._expected_disconnect:
            _LOGGER.debug("%s: Disconnected from device", self.name)
            return
        _LOGGER.warning("%s: Device unexpectedly disconnected", self.name)
        asyncio.create_task(self._reconnect())

    async def stop(self) -> None:
        """Stop the KDY BLE connection."""
        _LOGGER.debug("%s: Stop", self.name)
        await self._execute_disconnect()

    async def _execute_disconnect(self) -> None:
        """Execute disconnection."""
        async with self._connect_lock:
            client = self._client
            self._expected_disconnect = True
            self._client = None
            if client and client.is_connected:
                for char in (CHARACTERISTIC_FFF2, CHARACTERISTIC_FFF1):
                    try:
                        await client.stop_notify(char)
                    except BleakError:
                        _LOGGER.debug(
                            "%s: stop_notify %s failed",
                            self.name,
                            short_uuid(char),
                            exc_info=True,
                        )
                await client.disconnect()

    def register_callback(
        self, callback: Callable[[KdyState], None]
    ) -> Callable[[], None]:
        """Register a callback to be called when the state changes."""

        def unregister_callback() -> None:
            self._callbacks.remove(callback)

        self._callbacks.append(callback)
        return unregister_callback

    def _fire_callbacks(self) -> None:
        """Fire the callbacks."""
        for callback in self._callbacks:
            callback(self._state)

    def register_disconnected_callback(
        self, callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback to be called when disconnected."""

        def unregister_callback() -> None:
            self._disconnected_callbacks.remove(callback)

        self._disconnected_callbacks.append(callback)
        return unregister_callback

    def _fire_disconnected_callbacks(self) -> None:
        """Fire the disconnected callbacks."""
        for callback in self._disconnected_callbacks:
            callback()
