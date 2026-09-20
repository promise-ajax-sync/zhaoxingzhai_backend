from datetime import UTC, datetime
import json

import httpx

from app.core.config import Settings
from app.schemas.interpretation import (
    InterpretationRequest,
    InterpretationResponse,
    ReadingEvidence,
    StructuredReading,
)
from app.services.prompt_builder import PROMPT_VERSION, build_system_prompt, build_user_prompt
from app.services.provider import OpenAiCompatibleProvider, ProviderError


class InterpretationService:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._provider = OpenAiCompatibleProvider(settings, http_client)

    async def interpret(self, payload: InterpretationRequest) -> InterpretationResponse:
        if not self._settings.ai_enabled:
            return self._fallback(payload, "AI 服务尚未配置")

        try:
            result = await self._provider.generate(
                build_system_prompt(payload),
                build_user_prompt(payload),
            )
        except ProviderError as error:
            return self._fallback(payload, str(error))

        reading = self._parse_reading(result.content)
        return InterpretationResponse(
            content=self._reading_content(reading) if reading else result.content,
            source="remote",
            providerId=result.provider_id,
            modelId=result.model_id,
            promptVersion=PROMPT_VERSION,
            generatedAt=datetime.now(UTC),
            evidenceMethodId=payload.evidence.method_id,
            reading=reading,
        )

    @staticmethod
    def _fallback(payload: InterpretationRequest, reason: str) -> InterpretationResponse:
        sections = [payload.local_answer.strip(), f"判断依据：{payload.evidence.summary}"]
        counter = "；".join(item.detail for item in payload.evidence.counter_evidence if item.detail)
        limitations = "；".join(item.detail for item in payload.evidence.limitations if item.detail)
        if counter:
            sections.append(f"反向信息：{counter}")
        if limitations:
            sections.append(f"能力边界：{limitations}")
        reading = StructuredReading(
            headline=payload.local_answer.strip() or "请结合现实情况谨慎判断。",
            plainLanguage=payload.evidence.summary.strip() or payload.local_answer.strip(),
            evidence=[
                ReadingEvidence(label=item.label, explanation=item.detail)
                for item in (
                    payload.evidence.supporting_evidence
                    or payload.evidence.calculation_facts
                )[:4]
            ],
            risks=[item.detail for item in payload.evidence.counter_evidence[:3]],
            actions=[],
            boundary=limitations or "占卜解读用于辅助思考，重要决定请结合现实信息。",
            closing=(
                "先照顾好自己的节奏，再慢慢看变化就好啦 ( ˘͈ ᵕ ˘͈ )"
                if payload.question.topic in {"relationship", "wealth", "general"}
                else ""
            ),
        )
        return InterpretationResponse(
            content=InterpretationService._reading_content(reading),
            source="local_fallback",
            providerId="local",
            modelId="structured-reading",
            promptVersion=PROMPT_VERSION,
            generatedAt=datetime.now(UTC),
            evidenceMethodId=payload.evidence.method_id,
            fallbackReason=reason,
            reading=reading,
        )

    @staticmethod
    def _parse_reading(content: str) -> StructuredReading | None:
        raw = content.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1]).strip()
        try:
            return StructuredReading.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    @staticmethod
    def _reading_content(reading: StructuredReading) -> str:
        sections = [reading.headline, reading.plain_language]
        if reading.evidence:
            sections.append(
                "\n".join(
                    f"- {item.label}：{item.explanation}" for item in reading.evidence
                )
            )
        if reading.risks:
            sections.append("需要注意：\n" + "\n".join(f"- {item}" for item in reading.risks))
        if reading.actions:
            sections.append("建议怎么做：\n" + "\n".join(f"- {item}" for item in reading.actions))
        if reading.boundary:
            sections.append(reading.boundary)
        if reading.closing:
            sections.append(reading.closing)
        return "\n\n".join(section for section in sections if section)
