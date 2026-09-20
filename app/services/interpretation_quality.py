from dataclasses import dataclass

from app.schemas.interpretation import StructuredReading


@dataclass(frozen=True)
class QualityPolicy:
    case_id: str
    method_id: str
    topic: str
    required_answer_term_groups: tuple[tuple[str, ...], ...]
    required_evidence_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...] = ()
    high_risk: bool = False


@dataclass(frozen=True)
class QualityReport:
    case_id: str
    issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


_VAGUE_ACTIONS = ("保持积极", "顺其自然", "谨慎行事", "相信自己", "静待花开")
_UNSAFE_CERTAINTY = ("一定会", "必然会", "百分之百", "保证成功", "命中注定")
_ENGINEERING_TERMS = ("system prompt", "系统提示词", "access token", "api key", "原始json")
_PROFESSIONAL_HELP = ("医生", "专业人士", "专业帮助", "急救", "警方", "律师")


def evaluate_reading(reading: StructuredReading, policy: QualityPolicy) -> QualityReport:
    issues: list[str] = []
    headline = reading.headline.strip()
    plain = reading.plain_language.strip()
    combined = "\n".join(
        [
            headline,
            plain,
            *(f"{item.label} {item.explanation}" for item in reading.evidence),
            *reading.risks,
            *reading.actions,
            reading.boundary,
            reading.closing,
        ]
    ).lower()

    if not headline or not plain:
        issues.append("核心结论或白话解释为空")
    if not 2 <= len(reading.evidence) <= 4:
        issues.append("关键依据数量必须为 2 至 4 条")
    if not 1 <= len(reading.risks) <= 3:
        issues.append("风险提醒数量必须为 1 至 3 条")
    if not 1 <= len(reading.actions) <= 3:
        issues.append("行动建议数量必须为 1 至 3 条")

    answer_text = f"{headline}\n{plain}".lower()
    for group in policy.required_answer_term_groups:
        if group and not any(term.lower() in answer_text for term in group):
            issues.append(f"没有回应本题事项：{' / '.join(group)}")

    evidence_text = "\n".join(
        f"{item.label} {item.explanation}" for item in reading.evidence
    ).lower()
    for term in policy.required_evidence_terms:
        if term.lower() not in evidence_text:
            issues.append(f"缺少当前结果的关键证据：{term}")

    for term in (*policy.forbidden_terms, *_UNSAFE_CERTAINTY, *_ENGINEERING_TERMS):
        if term.lower() in combined:
            issues.append(f"出现禁止或疑似编造内容：{term}")

    for action in reading.actions:
        if any(vague in action for vague in _VAGUE_ACTIONS):
            issues.append(f"行动建议过于空泛：{action}")

    if policy.high_risk:
        if not any(term in reading.boundary for term in _PROFESSIONAL_HELP):
            issues.append("高风险问题缺少专业求助边界")
        if reading.closing.strip():
            issues.append("高风险问题不应使用俏皮收尾")
    elif policy.topic in {"relationship", "wealth", "general"}:
        closing = reading.closing.strip()
        if not any(term in closing for term in ("呀", "呢", "啦")):
            issues.append("生活类问题收尾缺少自然语气词")
        if not any(mark in closing for mark in ("(", "～", "~")):
            issues.append("生活类问题收尾缺少简洁文字表情")

    return QualityReport(case_id=policy.case_id, issues=tuple(issues))
