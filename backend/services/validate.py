DANANG_BBOX = {"lat_min": 15.9, "lat_max": 16.2, "lng_min": 107.9, "lng_max": 108.4}

def validate_record(record: dict) -> tuple[bool, str]:
    """Return (is_valid, reason). Reason rỗng nếu valid."""
    if record.get("speed", -1) < 0:
        return False, "speed_negative"
    if record.get("congestion_level") not in [1, 2, 3]:
        return False, "invalid_congestion_level"
    lat, lng = record.get("lat"), record.get("lng")
    if not (DANANG_BBOX["lat_min"] <= lat <= DANANG_BBOX["lat_max"] and
            DANANG_BBOX["lng_min"] <= lng <= DANANG_BBOX["lng_max"]):
        return False, "out_of_danang_bounds"
    return True, ""

def validate_batch(records: list) -> tuple[list, list]:
    """Return (valid_records, invalid_records)"""
    valid = []
    invalid = []
    for record in records:
        is_valid, reason = validate_record(record)
        if is_valid:
            valid.append(record)
        else:
            invalid.append({"record": record, "reason": reason})
    return valid, invalid