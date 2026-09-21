from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.services.sync_cursor import decode_sync_cursor, encode_sync_cursor


def test_sync_cursor_round_trip() -> None:
    updated_at = datetime(2026, 9, 21, 8, 30, tzinfo=UTC)
    resource_id = UUID("d10553ec-3434-48b5-bf7f-c5419a0b9540")

    encoded = encode_sync_cursor(updated_at, resource_id)

    assert decode_sync_cursor(encoded) == (updated_at, resource_id)


def test_invalid_sync_cursor_returns_bad_request() -> None:
    with pytest.raises(HTTPException) as captured:
        decode_sync_cursor("not-a-valid-cursor")

    assert captured.value.status_code == 400
