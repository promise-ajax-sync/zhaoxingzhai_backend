import pytest
from fastapi import HTTPException

from app.services.record_service import device_hash, require_sync_version


def test_device_hash_is_stable_and_does_not_store_raw_identifier() -> None:
    raw = "device-identifier-1234567890"
    first = device_hash(raw, "test-secret")
    second = device_hash(raw, "test-secret")

    assert first == second
    assert raw not in first
    assert len(first) == 64
    assert device_hash(raw, "another-secret") != first


def test_sync_version_accepts_current_version_and_legacy_client() -> None:
    require_sync_version(resource="case", base_version=3, current_version=3)
    require_sync_version(resource="case", base_version=None, current_version=3)


def test_sync_version_rejects_stale_write_with_current_version() -> None:
    with pytest.raises(HTTPException) as captured:
        require_sync_version(resource="record", base_version=2, current_version=4)

    assert captured.value.status_code == 409
    assert captured.value.detail == {
        "code": "sync_version_conflict",
        "resource": "record",
        "currentVersion": 4,
    }
