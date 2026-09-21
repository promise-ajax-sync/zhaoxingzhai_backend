import hashlib
import hmac
import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import AiInterpretation, Case, DivinationRecord, User
from app.schemas.records import AiInterpretationUpsertRequest, RecordUpsertRequest


def require_sync_version(
    *,
    resource: str,
    base_version: int | None,
    current_version: int,
) -> None:
    """Reject stale writes while keeping pre-version clients compatible."""
    if base_version is None or base_version == current_version:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "sync_version_conflict",
            "resource": resource,
            "currentVersion": current_version,
        },
    )


def device_hash(device_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), device_id.encode(), hashlib.sha256).hexdigest()


def require_device_id(request: Request) -> str:
    value = request.headers.get("x-device-id", "").strip()
    if len(value) < 16 or len(value) > 200 or not value.isascii():
        raise HTTPException(status_code=400, detail="缺少有效的设备标识")
    return value


async def get_or_create_user(
    session: AsyncSession,
    device_id: str,
    settings: Settings,
) -> User:
    hashed = device_hash(device_id, settings.app_device_hash_secret)
    user = await session.scalar(select(User).where(User.device_id_hash == hashed))
    if user is not None:
        return user
    user = User(device_id_hash=hashed, is_anonymous=True, is_active=True)
    session.add(user)
    await session.flush()
    return user


async def owned_record(
    session: AsyncSession,
    user_id: uuid.UUID,
    record_id: uuid.UUID,
    *,
    include_deleted: bool = False,
    for_update: bool = False,
) -> DivinationRecord:
    statement = select(DivinationRecord).where(
        DivinationRecord.id == record_id,
        DivinationRecord.user_id == user_id,
    )
    if not include_deleted:
        statement = statement.where(DivinationRecord.is_deleted.is_(False))
    if for_update:
        statement = statement.with_for_update()
    record = await session.scalar(statement)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


async def owned_case(
    session: AsyncSession,
    user_id: uuid.UUID,
    case_id: uuid.UUID,
    *,
    include_deleted: bool = False,
    for_update: bool = False,
) -> Case:
    statement = select(Case).where(Case.id == case_id, Case.user_id == user_id)
    if not include_deleted:
        statement = statement.where(Case.is_deleted.is_(False))
    if for_update:
        statement = statement.with_for_update()
    case = await session.scalar(statement)
    if case is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return case


def apply_record_payload(record: DivinationRecord, payload: RecordUpsertRequest) -> None:
    record.method_type = payload.method_type
    record.title = payload.title
    record.summary = payload.summary
    record.question = payload.question
    record.result_payload = payload.result_payload
    record.case_snapshot = payload.case_snapshot
    record.algorithm_id = payload.algorithm_id
    record.algorithm_version = payload.algorithm_version
    record.schema_version = payload.schema_version
    record.occurred_at = payload.occurred_at
    record.is_deleted = False


def new_ai_interpretation(
    record: DivinationRecord,
    payload: AiInterpretationUpsertRequest,
) -> AiInterpretation:
    return AiInterpretation(
        record=record,
        content=payload.content,
        source=payload.source,
        provider_id=payload.provider_id,
        model_id=payload.model_id,
        prompt_version=payload.prompt_version,
        evidence_method_id=payload.evidence_method_id,
        answer_style=payload.answer_style,
        fallback_reason=payload.fallback_reason,
        generated_at=payload.generated_at,
        request_id=payload.request_id,
        structured_reading=payload.structured_reading,
    )
