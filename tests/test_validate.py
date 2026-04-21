import pytest
from backend.services.validate import validate_record, validate_batch

def test_negative_speed():
    record = {"speed": -5, "congestion_level": 2, "lat": 16.0, "lng": 108.0}
    is_valid, reason = validate_record(record)
    assert is_valid == False
    assert reason == "speed_negative"

def test_invalid_congestion_level():
    record = {"speed": 50, "congestion_level": 4, "lat": 16.0, "lng": 108.0}
    is_valid, reason = validate_record(record)
    assert is_valid == False
    assert reason == "invalid_congestion_level"

def test_out_of_danang_bounds():
    record = {"speed": 50, "congestion_level": 2, "lat": 17.0, "lng": 108.0}  # lat ngoài bbox
    is_valid, reason = validate_record(record)
    assert is_valid == False
    assert reason == "out_of_danang_bounds"

def test_valid_record():
    record = {"speed": 50, "congestion_level": 2, "lat": 16.0, "lng": 108.0}
    is_valid, reason = validate_record(record)
    assert is_valid == True
    assert reason == ""

def test_validate_batch():
    records = [
        {"speed": 50, "congestion_level": 2, "lat": 16.0, "lng": 108.0},  # valid
        {"speed": -5, "congestion_level": 2, "lat": 16.0, "lng": 108.0},  # invalid
        {"speed": 30, "congestion_level": 1, "lat": 15.8, "lng": 108.0},  # invalid lat
    ]
    valid, invalid = validate_batch(records)
    assert len(valid) == 1
    assert len(invalid) == 2
    assert invalid[0]["reason"] == "speed_negative"
    assert invalid[1]["reason"] == "out_of_danang_bounds"