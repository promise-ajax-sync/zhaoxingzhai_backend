from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.interpretation import ApiModel


class RecordUpsertRequest(ApiModel):
    client_record_id: str = Field(alias="clientRecordId", min_length=1, max_length=200)
    method_type: str = Field(alias="methodType", min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(max_length=12000)
    question: dict[str, Any] | None = None
    result_payload: dict[str, Any] = Field(alias="resultPayload")
    case_snapshot: dict[str, Any] | None = Field(default=None, alias="caseSnapshot")
    algorithm_id: str = Field(alias="algorithmId", max_length=128)
    algorithm_version: int = Field(alias="algorithmVersion", ge=0)
    schema_version: str = Field(alias="schemaVersion", max_length=64)
    occurred_at: datetime = Field(alias="occurredAt")


class RecordResponse(RecordUpsertRequest):
    id: UUID
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    ai_interpretation: "AiInterpretationRecordResponse | None" = Field(
        default=None,
        alias="aiInterpretation",
    )


class CaseUpsertRequest(ApiModel):
    client_id: str = Field(alias="clientId", min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    profile: dict[str, Any]


class CaseResponse(CaseUpsertRequest):
    id: UUID
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AiInterpretationUpsertRequest(ApiModel):
    content: str = Field(min_length=1, max_length=100000)
    source: Literal["remote", "local_fallback"]
    provider_id: str = Field(alias="providerId", max_length=128)
    model_id: str = Field(alias="modelId", max_length=255)
    prompt_version: int = Field(alias="promptVersion", ge=0)
    evidence_method_id: str = Field(alias="evidenceMethodId", max_length=128)
    answer_style: str = Field(alias="answerStyle", max_length=32)
    fallback_reason: str | None = Field(default=None, alias="fallbackReason", max_length=12000)
    generated_at: datetime = Field(alias="generatedAt")
    request_id: str | None = Field(default=None, alias="requestId", max_length=128)
    structured_reading: dict[str, Any] | None = Field(
        default=None,
        alias="structuredReading",
    )


class AiInterpretationRecordResponse(AiInterpretationUpsertRequest):
    id: UUID
    record_id: UUID = Field(alias="recordId")
    created_at: datetime = Field(alias="createdAt")


RecordResponse.model_rebuild()
