"""Tests for KDY BLE constants and device detection."""

from tests.kdy.import_helper import load_kdy_module

const = load_kdy_module("const")


def test_service_and_characteristic_uuids() -> None:
    assert const.SERVICE_UUID == "0000fff0-0000-1000-8000-00805f9b34fb"
    assert const.CHARACTERISTIC_FFF1 == "0000fff1-0000-1000-8000-00805f9b34fb"
    assert const.CHARACTERISTIC_FFF2 == "0000fff2-0000-1000-8000-00805f9b34fb"
    assert const.CHARACTERISTIC_FFF3 == "0000fff3-0000-1000-8000-00805f9b34fb"


def test_short_uuid() -> None:
    assert const.short_uuid(const.SERVICE_UUID) == "FFF0"
    assert const.short_uuid(const.CHARACTERISTIC_FFF1) == "FFF1"
    assert const.short_uuid(const.CHARACTERISTIC_FFF2) == "FFF2"
    assert const.short_uuid(const.CHARACTERISTIC_FFF3) == "FFF3"


def test_is_kdy_sauna_name() -> None:
    assert const.is_kdy_sauna_name("KDYSauna-10") is True
    assert const.is_kdy_sauna_name("KDYSauna") is True
    assert const.is_kdy_sauna_name("SAUNA-OSLO") is False
    assert const.is_kdy_sauna_name(None) is False
    assert const.is_kdy_sauna_name("") is False
