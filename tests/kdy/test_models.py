"""Tests for KDY status parsing — only real captured payloads."""

import pytest

from tests.kdy.import_helper import load_kdy_module

load_kdy_module("const")  # models imports .const
models = load_kdy_module("models")
KdyState = models.KdyState
InvalidStatusPacket = models.InvalidStatusPacket

# Real hardware capture from KDYSauna-10 (Artsauna_KDYSauna10_BLE-Protokoll.md):
# power ON, 48 min remaining, 32 °C actual, 35 °C target
CAPTURED_STATUS = bytes.fromhex(
    "AA0130302023000000000000000000000100000000CC"
)


def test_parse_captured_status() -> None:
    state = KdyState.from_ble_status(CAPTURED_STATUS)

    assert state.power is True
    assert state.remaining_minutes == 0x30  # 48 minutes
    assert state.current_temp == 0x20  # 32 °C
    assert state.target_temp == 0x23  # 35 °C
    assert state.raw == CAPTURED_STATUS


def test_raw_payload_retained() -> None:
    state = KdyState.from_ble_status(CAPTURED_STATUS)
    assert state.raw.hex() == CAPTURED_STATUS.hex()


def test_is_status_frame() -> None:
    assert KdyState.is_status_frame(CAPTURED_STATUS) is True
    assert KdyState.is_status_frame(b"\xaa\x00") is False
    assert KdyState.is_status_frame(bytes(22)) is False


def test_invalid_frame_raises() -> None:
    with pytest.raises(InvalidStatusPacket):
        KdyState.from_ble_status(b"\xff\xaa\x05ASOK3")


def test_power_off_observed_values() -> None:
    """Power OFF uses observed byte-1 value 0x00; other fields from same framing."""
    payload = bytearray(CAPTURED_STATUS)
    payload[1] = 0x00
    state = KdyState.from_ble_status(payload)
    assert state.power is False
    assert state.raw == bytes(payload)


def test_format_known_fields_mentions_unknowns() -> None:
    state = KdyState.from_ble_status(CAPTURED_STATUS)
    text = state.format_known_fields()
    assert "ON" in text
    assert "48" in text
    assert "unknown" in text.lower()
