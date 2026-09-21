import base64
import json
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException


def encode_sync_cursor(updated_at: datetime, resource_id: UUID) -> str:
    payload = json.dumps(
        {"updatedAt": updated_at.isoformat(), "id": str(resource_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_sync_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if value is None or not value.strip():
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        return datetime.fromisoformat(payload["updatedAt"]), UUID(payload["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="同步游标无效") from None
