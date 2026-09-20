from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.models import AiInterpretation, Case, DivinationRecord
from app.schemas.interpretation import InterpretationRequest, InterpretationResponse
from app.schemas.records import (
    AiInterpretationRecordResponse,
    AiInterpretationUpsertRequest,
    RecordResponse,
    RecordUpsertRequest,
    CaseResponse,
    CaseUpsertRequest,
)
from app.services.interpretation_service import InterpretationService
from app.services.auth_service import request_user
from app.services.record_service import (
    apply_record_payload,
    new_ai_interpretation,
    owned_record,
    owned_case,
)

router = APIRouter()


def case_response(case: Case) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        clientId=case.client_id,
        name=case.name,
        profile=case.profile,
        createdAt=case.created_at,
        updatedAt=case.updated_at,
    )


@router.post("/api/v1/cases", response_model=CaseResponse)
async def upsert_case(
    payload: CaseUpsertRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CaseResponse:
    user = await request_user(session, request, get_settings())
    case = await session.scalar(
        select(Case).where(Case.user_id == user.id, Case.client_id == payload.client_id)
    )
    if case is None:
        case = Case(user_id=user.id, client_id=payload.client_id)
        session.add(case)
    case.name = payload.name
    case.profile = payload.profile
    case.is_deleted = False
    await session.flush()
    unlinked_records = (
        await session.scalars(
            select(DivinationRecord).where(
                DivinationRecord.user_id == user.id,
                DivinationRecord.case_id.is_(None),
            )
        )
    ).all()
    for record in unlinked_records:
        snapshot = record.case_snapshot
        if isinstance(snapshot, dict) and snapshot.get("caseId") == payload.client_id:
            record.case_id = case.id
    await session.commit()
    await session.refresh(case)
    return case_response(case)


@router.get("/api/v1/cases", response_model=list[CaseResponse])
async def list_cases(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[CaseResponse]:
    user = await request_user(session, request, get_settings())
    await session.commit()
    cases = (
        await session.scalars(
            select(Case)
            .where(Case.user_id == user.id, Case.is_deleted.is_(False))
            .order_by(Case.updated_at.desc())
        )
    ).all()
    return [case_response(case) for case in cases]


@router.get("/api/v1/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CaseResponse:
    user = await request_user(session, request, get_settings())
    await session.commit()
    return case_response(await owned_case(session, user.id, case_id))


@router.delete("/api/v1/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await request_user(session, request, get_settings())
    case = await owned_case(session, user.id, case_id)
    case.is_deleted = True
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "zhaoxingzhai-backend"}


@router.post("/api/v1/interpret", response_model=InterpretationResponse)
async def interpret(payload: InterpretationRequest, request: Request) -> InterpretationResponse:
    service = InterpretationService(
        settings=get_settings(),
        http_client=request.app.state.http_client,
    )
    return await service.interpret(payload)


def ai_record_response(interpretation: AiInterpretation) -> AiInterpretationRecordResponse:
    return AiInterpretationRecordResponse(
        id=interpretation.id,
        recordId=interpretation.record_id,
        content=interpretation.content,
        source=interpretation.source,
        providerId=interpretation.provider_id,
        modelId=interpretation.model_id,
        promptVersion=interpretation.prompt_version,
        evidenceMethodId=interpretation.evidence_method_id,
        answerStyle=interpretation.answer_style,
        fallbackReason=interpretation.fallback_reason,
        generatedAt=interpretation.generated_at,
        requestId=interpretation.request_id,
        structuredReading=interpretation.structured_reading,
        createdAt=interpretation.created_at,
    )


def record_response(
    record: DivinationRecord,
    interpretation: AiInterpretation | None = None,
) -> RecordResponse:
    return RecordResponse(
        id=record.id,
        clientRecordId=record.client_record_id,
        methodType=record.method_type,
        title=record.title,
        summary=record.summary,
        question=record.question,
        resultPayload=record.result_payload,
        caseSnapshot=record.case_snapshot,
        algorithmId=record.algorithm_id,
        algorithmVersion=record.algorithm_version,
        schemaVersion=record.schema_version,
        occurredAt=record.occurred_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        aiInterpretation=(
            ai_record_response(interpretation) if interpretation is not None else None
        ),
    )


async def latest_interpretations(
    session: AsyncSession,
    record_ids: list[UUID],
) -> dict[UUID, AiInterpretation]:
    if not record_ids:
        return {}
    interpretations = (
        await session.scalars(
            select(AiInterpretation)
            .where(AiInterpretation.record_id.in_(record_ids))
            .order_by(AiInterpretation.record_id, AiInterpretation.created_at.desc())
        )
    ).all()
    latest: dict[UUID, AiInterpretation] = {}
    for interpretation in interpretations:
        latest.setdefault(interpretation.record_id, interpretation)
    return latest


@router.post("/api/v1/records", response_model=RecordResponse)
async def upsert_record(
    payload: RecordUpsertRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RecordResponse:
    user = await request_user(session, request, get_settings())
    record = await session.scalar(
        select(DivinationRecord).where(
            DivinationRecord.user_id == user.id,
            DivinationRecord.client_record_id == payload.client_record_id,
        )
    )
    if record is None:
        record = DivinationRecord(
            user_id=user.id,
            client_record_id=payload.client_record_id,
            method_type=payload.method_type,
            title=payload.title,
            summary=payload.summary,
            result_payload=payload.result_payload,
            algorithm_id=payload.algorithm_id,
            algorithm_version=payload.algorithm_version,
            schema_version=payload.schema_version,
            occurred_at=payload.occurred_at,
        )
        session.add(record)
    apply_record_payload(record, payload)
    snapshot = payload.case_snapshot
    if isinstance(snapshot, dict) and isinstance(snapshot.get("caseId"), str):
        linked_case = await session.scalar(
            select(Case).where(
                Case.user_id == user.id,
                Case.client_id == snapshot["caseId"],
                Case.is_deleted.is_(False),
            )
        )
        record.case_id = linked_case.id if linked_case is not None else None
    await session.commit()
    await session.refresh(record)
    return record_response(record)


@router.get("/api/v1/records", response_model=list[RecordResponse])
async def list_records(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RecordResponse]:
    user = await request_user(session, request, get_settings())
    await session.commit()
    records = (
        await session.scalars(
            select(DivinationRecord)
            .where(
                DivinationRecord.user_id == user.id,
                DivinationRecord.is_deleted.is_(False),
            )
            .order_by(DivinationRecord.occurred_at.desc())
            .limit(limit)
        )
    ).all()
    interpretations = await latest_interpretations(
        session,
        [record.id for record in records],
    )
    return [record_response(record, interpretations.get(record.id)) for record in records]


@router.get("/api/v1/records/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RecordResponse:
    user = await request_user(session, request, get_settings())
    await session.commit()
    record = await owned_record(session, user.id, record_id)
    interpretations = await latest_interpretations(session, [record.id])
    return record_response(record, interpretations.get(record.id))


@router.delete("/api/v1/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(
    record_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await request_user(session, request, get_settings())
    record = await owned_record(session, user.id, record_id)
    record.is_deleted = True
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/api/v1/records/{record_id}/ai-interpretation",
    response_model=AiInterpretationRecordResponse,
)
async def add_ai_interpretation(
    record_id: UUID,
    payload: AiInterpretationUpsertRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AiInterpretationRecordResponse:
    user = await request_user(session, request, get_settings())
    record = await owned_record(session, user.id, record_id)
    interpretation = await session.scalar(
        select(AiInterpretation)
        .where(AiInterpretation.record_id == record.id)
        .order_by(AiInterpretation.created_at.desc())
        .limit(1)
    )
    if interpretation is None:
        interpretation = new_ai_interpretation(record, payload)
        session.add(interpretation)
    else:
        interpretation.content = payload.content
        interpretation.source = payload.source
        interpretation.provider_id = payload.provider_id
        interpretation.model_id = payload.model_id
        interpretation.prompt_version = payload.prompt_version
        interpretation.evidence_method_id = payload.evidence_method_id
        interpretation.answer_style = payload.answer_style
        interpretation.fallback_reason = payload.fallback_reason
        interpretation.generated_at = payload.generated_at
        interpretation.request_id = payload.request_id
        interpretation.structured_reading = payload.structured_reading
    await session.commit()
    await session.refresh(interpretation)
    return ai_record_response(interpretation)
