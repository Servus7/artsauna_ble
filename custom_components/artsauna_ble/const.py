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

"""Constants for the Artsauna-BLE integration."""

DOMAIN = "artsauna_ble"

CONF_DEVICE_TYPE = "device_type"
DEVICE_TYPE_ARTSAUNA = "artsauna"
DEVICE_TYPE_KDY = "kdy"


def device_type_for_name(name: str | None) -> str:
    """Classify device type from advertised local name."""
    if name and name.startswith("KDYSauna"):
        return DEVICE_TYPE_KDY
    return DEVICE_TYPE_ARTSAUNA

