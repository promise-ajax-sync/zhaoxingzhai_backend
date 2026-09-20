from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class QuestionPayload(ApiModel):
    raw_text: str = Field(alias="rawText", min_length=1, max_length=4000)
    topic: str = Field(default="general", max_length=64)
    intent: str = Field(default="general", max_length=64)
    intent_label: str | None = Field(default=None, alias="intentLabel", max_length=64)


class EvidenceItem(ApiModel):
    id: str = Field(max_length=128)
    label: str = Field(max_length=128)
    detail: str = Field(max_length=8000)


class EvidencePayload(ApiModel):
    method_id: str = Field(alias="methodId", max_length=64)
    version: int = Field(ge=0)
    calculation_facts: list[EvidenceItem] = Field(alias="calculationFacts", max_length=64)
    supporting_evidence: list[EvidenceItem] = Field(alias="supportingEvidence", max_length=64)
    counter_evidence: list[EvidenceItem] = Field(alias="counterEvidence", max_length=64)
    limitations: list[EvidenceItem] = Field(max_length=64)
    summary: str = Field(max_length=8000)


class InterpretationRequest(ApiModel):
    question: QuestionPayload
    evidence: EvidencePayload
    local_answer: str = Field(alias="localAnswer", max_length=12000)
    method_label: str = Field(alias="methodLabel", max_length=128)
    answer_style: Literal["balanced", "chat", "fortune-master", "professional"] = Field(
        default="balanced", alias="answerStyle"
    )
    locale: str = Field(default="zh-CN", max_length=32)


class ReadingEvidence(ApiModel):
    label: str = Field(max_length=128)
    explanation: str = Field(max_length=1000)


class StructuredReading(ApiModel):
    headline: str = Field(max_length=500)
    plain_language: str = Field(alias="plainLanguage", max_length=4000)
    evidence: list[ReadingEvidence] = Field(max_length=6)
    risks: list[str] = Field(max_length=5)
    actions: list[str] = Field(max_length=5)
    boundary: str = Field(default="", max_length=1000)
    closing: str = Field(default="", max_length=300)


class InterpretationResponse(ApiModel):
    content: str
    source: Literal["remote", "local_fallback"]
    provider_id: str = Field(alias="providerId")
    model_id: str = Field(alias="modelId")
    prompt_version: int = Field(alias="promptVersion")
    generated_at: datetime = Field(alias="generatedAt")
    evidence_method_id: str = Field(alias="evidenceMethodId")
    fallback_reason: str | None = Field(default=None, alias="fallbackReason")
    reading: StructuredReading | None = None
