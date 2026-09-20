import json
from pathlib import Path

from app.schemas.interpretation import StructuredReading
from app.services.interpretation_eval_dataset import load_quality_cases, policy_from_case
from app.services.interpretation_quality import QualityPolicy, evaluate_reading


CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "interpretation_cases.json"


def _cases() -> list[dict]:
    return list(load_quality_cases(CASES_PATH).values())


def _policy(item: dict) -> QualityPolicy:
    return policy_from_case(item)


def test_all_fixed_quality_cases_pass() -> None:
    cases = _cases()
    assert {item["methodId"] for item in cases} == {
        "meihua",
        "tarot",
        "xiaoliuren",
        "ssgw",
        "daily-hexagram",
    }
    for item in cases:
        reading = StructuredReading.model_validate(item["reading"])
        report = evaluate_reading(reading, _policy(item))
        assert report.passed, f"{item['id']}: {report.issues}"


def test_evaluator_detects_invented_evidence_and_unsafe_certainty() -> None:
    item = _cases()[0]
    reading = StructuredReading.model_validate(item["reading"]).model_copy(
        update={
            "plain_language": "恋人牌说明这个合作一定会成功。",
        }
    )

    report = evaluate_reading(reading, _policy(item))

    assert not report.passed
    assert any("恋人牌" in issue for issue in report.issues)
    assert any("一定会" in issue for issue in report.issues)


def test_evaluator_detects_missing_grounding_and_vague_action() -> None:
    item = _cases()[2]
    reading = StructuredReading.model_validate(item["reading"]).model_copy(
        update={
            "evidence": [],
            "actions": ["保持积极，顺其自然。"],
        }
    )

    report = evaluate_reading(reading, _policy(item))

    assert not report.passed
    assert any("关键依据数量" in issue for issue in report.issues)
    assert any("行动建议过于空泛" in issue for issue in report.issues)


def test_evaluator_requires_professional_boundary_for_high_risk_case() -> None:
    item = next(item for item in _cases() if item.get("highRisk"))
    reading = StructuredReading.model_validate(item["reading"]).model_copy(
        update={"boundary": "仅供参考。", "closing": "放轻松呀 (^-^)"}
    )

    report = evaluate_reading(reading, _policy(item))

    assert not report.passed
    assert "高风险问题缺少专业求助边界" in report.issues
    assert "高风险问题不应使用俏皮收尾" in report.issues


def test_evaluator_detects_off_topic_answer_for_compound_question() -> None:
    item = next(item for item in _cases() if item["id"] == "tarot-compound-choice")
    reading = StructuredReading.model_validate(item["reading"]).model_copy(
        update={
            "headline": "你最近需要注意休息。",
            "plain_language": "目前的重点是调整作息和情绪。",
        }
    )

    report = evaluate_reading(reading, _policy(item))

    assert not report.passed
    assert sum("没有回应本题事项" in issue for issue in report.issues) == 2
