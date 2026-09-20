import json
import uuid
from pathlib import Path

from scripts.evaluate_saved_interpretations import evaluate_file


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "interpretation_cases.json"


def test_saved_output_example_passes() -> None:
    passed, total = evaluate_file(
        ROOT / "evals" / "saved_outputs.example.json",
        CASES_PATH,
    )

    assert (passed, total) == (1, 1)


def test_saved_output_reports_unknown_case_and_bad_reading() -> None:
    outputs = ROOT / ".test-media" / f"saved-outputs-{uuid.uuid4().hex}.json"
    outputs.parent.mkdir(exist_ok=True)
    try:
        outputs.write_text(
            json.dumps(
                [
                    {"caseId": "missing-case", "reading": {}},
                    {"caseId": "meihua-career-progress", "reading": {}},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        passed, total = evaluate_file(outputs, CASES_PATH)

        assert (passed, total) == (0, 2)
    finally:
        outputs.unlink(missing_ok=True)
