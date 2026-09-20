import json
from pathlib import Path
from typing import Any

from app.services.interpretation_quality import QualityPolicy


def load_quality_cases(path: Path) -> dict[str, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("评测样本文件必须是 JSON 数组")
    cases: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("评测样本缺少有效 id")
        if item["id"] in cases:
            raise ValueError(f"评测样本 id 重复：{item['id']}")
        cases[item["id"]] = item
    return cases


def policy_from_case(item: dict[str, Any]) -> QualityPolicy:
    groups = item.get("requiredAnswerTermGroups")
    answer_groups = (
        tuple(tuple(str(term) for term in group) for group in groups)
        if groups is not None
        else (tuple(str(term) for term in item["requiredAnswerTerms"]),)
    )
    return QualityPolicy(
        case_id=item["id"],
        method_id=item["methodId"],
        topic=item["topic"],
        required_answer_term_groups=answer_groups,
        required_evidence_terms=tuple(item["requiredEvidenceTerms"]),
        forbidden_terms=tuple(item.get("forbiddenTerms", [])),
        high_risk=bool(item.get("highRisk", False)),
    )
