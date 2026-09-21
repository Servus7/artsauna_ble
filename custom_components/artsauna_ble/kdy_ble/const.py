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

"""KDY Sauna BLE constants.

Confidence labels used in comments:
  verified  — confirmed against hardware GATT / frame framing
  observed  — matched live status packets on KDYSauna-10
  unknown   — present in frames; meaning not established (do not invent)
"""

from __future__ import annotations

# verified — GATT service and characteristics on KDYSauna-10
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_FFF1 = "0000fff1-0000-1000-8000-00805f9b34fb"  # write-without-response, notify
CHARACTERISTIC_FFF2 = "0000fff2-0000-1000-8000-00805f9b34fb"  # read, notify (status)
CHARACTERISTIC_FFF3 = "0000fff3-0000-1000-8000-00805f9b34fb"  # write-without-response; unused in phase 1

# observed — advertised local name prefix
DEVICE_NAME_PREFIXES = ("KDYSauna",)

# verified — 22-byte status frame on FFF2
STATUS_PACKET_LENGTH = 22
STATUS_START = 0xAA  # verified — byte 0
STATUS_END = 0xCC  # verified — byte 21

# observed — byte offsets in the AA…CC status frame (hardware capture)
# Byte 1: power 00=OFF, 01=ON
# Bytes 2–3: remaining minutes (both match; value is decimal minutes as hex)
# Byte 4: actual / current temperature °C
# Byte 5: target temperature °C
# Bytes 6–20: unknown
OFFSET_POWER = 1
OFFSET_REMAINING_MINUTES = 2
OFFSET_CURRENT_TEMP = 4
OFFSET_TARGET_TEMP = 5


def is_kdy_sauna_name(name: str | None) -> bool:
    """Return True if the advertised name matches known KDYSauna devices."""
    if not name:
        return False
    return name.startswith(DEVICE_NAME_PREFIXES)


def short_uuid(uuid: str) -> str:
    """Return the 16-bit style label for a Bluetooth UUID when possible."""
    normalized = uuid.lower()
    if normalized.startswith("0000") and normalized.endswith(
        "-0000-1000-8000-00805f9b34fb"
    ):
        return normalized[4:8].upper()
    return uuid
