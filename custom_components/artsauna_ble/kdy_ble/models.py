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

"""KDY Sauna BLE state model.

Only hardware-verified / high-confidence observed fields are decoded.
Unknown bytes remain in ``raw`` and are never assigned meaning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .const import (
    OFFSET_CURRENT_TEMP,
    OFFSET_POWER,
    OFFSET_REMAINING_MINUTES,
    OFFSET_TARGET_TEMP,
    STATUS_END,
    STATUS_PACKET_LENGTH,
    STATUS_START,
)


class InvalidStatusPacket(ValueError):
    """Raised when a payload is not a valid 22-byte AA…CC status frame."""


@dataclass(frozen=True)
class KdyState:
    """Decoded KDY status.

    Fields other than ``raw`` are only set from observed offsets.
    Bytes 6–20 are intentionally not exposed as named fields (unknown).
    """

    power: bool = False  # observed — byte 1
    remaining_minutes: int = 0  # observed — bytes 2–3
    current_temp: int = 0  # observed — byte 4 (°C)
    target_temp: int = 0  # observed — byte 5 (°C)
    raw: bytes = field(default_factory=bytes)  # verified — full notification payload

    @staticmethod
    def is_status_frame(data: bytes | bytearray) -> bool:
        """Return True if data looks like a verified AA…CC status frame."""
        return (
            len(data) == STATUS_PACKET_LENGTH
            and data[0] == STATUS_START
            and data[-1] == STATUS_END
        )

    @classmethod
    def from_ble_status(cls, data: bytes | bytearray) -> KdyState:
        """Parse known fields from a status notification.

        Raises InvalidStatusPacket if framing is not verified AA…CC / 22 bytes.
        """
        payload = bytes(data)
        if not cls.is_status_frame(payload):
            raise InvalidStatusPacket(
                f"Expected {STATUS_PACKET_LENGTH}-byte AA…CC frame, "
                f"got len={len(payload)} hex={payload.hex()}"
            )

        # observed: bytes 2 and 3 both carry remaining minutes and match
        remaining = payload[OFFSET_REMAINING_MINUTES]

        return cls(
            power=payload[OFFSET_POWER] != 0,
            remaining_minutes=remaining,
            current_temp=payload[OFFSET_CURRENT_TEMP],
            target_temp=payload[OFFSET_TARGET_TEMP],
            raw=payload,
        )

    def format_known_fields(self) -> str:
        """Human-readable known fields for debug logs."""
        return (
            f"Power: {'ON' if self.power else 'OFF'}; "
            f"Remaining: {self.remaining_minutes} min; "
            f"Current: {self.current_temp} °C; "
            f"Target: {self.target_temp} °C; "
            f"Timer/Light/RGB: unknown"
        )
