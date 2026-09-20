from app.services.record_service import device_hash


def test_device_hash_is_stable_and_does_not_store_raw_identifier() -> None:
    raw = "device-identifier-1234567890"
    first = device_hash(raw, "test-secret")
    second = device_hash(raw, "test-secret")

    assert first == second
    assert raw not in first
    assert len(first) == 64
    assert device_hash(raw, "another-secret") != first
