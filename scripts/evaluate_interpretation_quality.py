from pathlib import Path

from app.schemas.interpretation import StructuredReading
from app.services.interpretation_eval_dataset import load_quality_cases, policy_from_case
from app.services.interpretation_quality import evaluate_reading


def main() -> int:
    cases_path = Path(__file__).resolve().parents[1] / "evals" / "interpretation_cases.json"
    cases = load_quality_cases(cases_path)
    failed = 0
    for item in cases.values():
        policy = policy_from_case(item)
        reading = StructuredReading.model_validate(item["reading"])
        report = evaluate_reading(reading, policy)
        if report.passed:
            print(f"PASS {report.case_id}")
            continue
        failed += 1
        print(f"FAIL {report.case_id}")
        for issue in report.issues:
            print(f"  - {issue}")
    print(f"quality-eval: {len(cases) - failed}/{len(cases)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
