import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.interpretation import StructuredReading
from app.services.interpretation_eval_dataset import load_quality_cases, policy_from_case
from app.services.interpretation_quality import evaluate_reading


def evaluate_file(outputs_path: Path, cases_path: Path) -> tuple[int, int]:
    cases = load_quality_cases(cases_path)
    raw_outputs = json.loads(outputs_path.read_text(encoding="utf-8"))
    if not isinstance(raw_outputs, list):
        raise ValueError("AI 输出文件必须是 JSON 数组")

    passed = 0
    for index, item in enumerate(raw_outputs, start=1):
        if not isinstance(item, dict):
            print(f"FAIL output-{index}\n  - 输出项必须是 JSON 对象")
            continue
        case_id = str(item.get("caseId", "")).strip()
        case = cases.get(case_id)
        label = case_id or f"output-{index}"
        if case is None:
            print(f"FAIL {label}\n  - 找不到对应的固定评测样本")
            continue
        reading_raw = item.get("reading")
        try:
            reading = StructuredReading.model_validate(reading_raw)
        except ValidationError as error:
            print(f"FAIL {label}\n  - 结构化回答格式无效：{error.errors()[0]['msg']}")
            continue
        report = evaluate_reading(reading, policy_from_case(case))
        metadata = " ".join(
            value
            for value in (
                f"model={item['modelId']}" if item.get("modelId") else "",
                f"prompt={item['promptVersion']}" if item.get("promptVersion") else "",
            )
            if value
        )
        suffix = f" ({metadata})" if metadata else ""
        if report.passed:
            passed += 1
            print(f"PASS {label}{suffix}")
            continue
        print(f"FAIL {label}{suffix}")
        for issue in report.issues:
            print(f"  - {issue}")
    print(f"saved-output-eval: {passed}/{len(raw_outputs)} passed")
    return passed, len(raw_outputs)


def main() -> int:
    backend_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="离线评分已保存的真实 AI 结构化回答")
    parser.add_argument("outputs", type=Path, help="保存的 AI 回答 JSON 文件")
    parser.add_argument(
        "--cases",
        type=Path,
        default=backend_root / "evals" / "interpretation_cases.json",
        help="固定评测样本文件",
    )
    args = parser.parse_args()
    passed, total = evaluate_file(args.outputs, args.cases)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
