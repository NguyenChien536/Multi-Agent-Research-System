"""Generate public synthetic demo inputs and verify the actual fixed routine.

No network, API key, database or LLM calls. Run from the repository root:
    .\.venv\Scripts\python.exe scripts/prepare-demo.py
Requires Python 3.11+; the fixture check itself uses only the standard library.
"""
import asyncio
import csv
import hashlib
import io
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.experiment_runner import InvalidInputError, parse_csv_dataset
from app.services.fieldwork_intake import validate_fieldwork_result
from app.services.isolated_experiment import run_tabular_regression_isolated, verify_tabular_repeatability_isolated

OUTPUT = ROOT / "examples" / "demo"

QUESTIONS = {
    "review": (
        "Under what conditions does spaced practice improve delayed retention compared with "
        "massed practice in adult or university learners? Prepare a critical narrative review. "
        "Compare practice schedules, retention intervals, outcome measures and populations, "
        "including conflicting findings and limits on transfer. Use relevant primary research "
        "and credible scholarly syntheses, and cite the evidence actually retrieved. Report "
        "the real search queries, index providers, eligibility criteria and search limitations; "
        "do not claim an exhaustive systematic review. Write academic English prose with "
        "meaningful subsections in substantial sections and explain any figures or tables. "
        "Distinguish supported conclusions from tentative research gaps."
    ),
    "computational": (
        "On the supplied SYNTHETIC electricity-demand CSV, how does the supported "
        "tabular_regression_v1 Ridge regression routine compare with a training-mean baseline "
        "on its recorded held-out split? Use temperature and occupied_hours to predict target. "
        "Run the supported routine and report its actual MAE, RMSE and R-squared, train-only "
        "preprocessing, split, seed and repeatability. Present a baseline comparison table and "
        "explain the generated figures. Write a computational paper-style draft with meaningful "
        "Methods, Experimental Setup, Results and Discussion subsections. Literature is for "
        "background, not a substitute for measured results. This is a synthetic demonstration, "
        "not a novel algorithm, causal study or real-world forecasting validation. Do not claim "
        "cross-validation, significance tests or multiple seeds were run."
    ),
    "human": (
        "How can an exploratory descriptive survey characterize perceived usefulness and "
        "verification effort when university students use AI research assistants? Prepare a "
        "protocol, then wait for a result file and provenance. For this SOFTWARE DEMONSTRATION "
        "I will upload 24 SYNTHETIC responses, not data collected from real people. After upload, "
        "write an empirical-style draft with meaningful subsections, explicitly labeling the "
        "data as synthetic in the Abstract, Methods, Results and Conclusion. Report only "
        "uploaded or computed descriptive statistics, specifying sample versus population SD. "
        "Do not invent recruitment, ethics approval, instrument validation, p-values, causal "
        "effects or generalizability. Explain how genuine future data collection would differ."
    ),
}


def csv_text(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def write(name, value):
    text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    (OUTPUT / name).write_bytes(text.encode("utf-8"))


async def prepare():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    electricity = csv_text(["temperature", "occupied_hours", "target"], [
        [15 + i * 7 % 24, 1 + i * 5 % 12,
         f"{40 + 2.4 * (15 + i * 7 % 24) + 4.5 * (1 + i * 5 % 12) + math.sin(i) * 2:.6f}"]
        for i in range(120)
    ])
    # Constant features contain no predictive information. The fixed routine must
    # preserve a non-improvement result rather than inventing a winning model.
    negative = csv_text(["temperature", "occupied_hours", "target"], [
        [20, 6, f"{100 + math.sin(i) * 12:.6f}"] for i in range(120)
    ])
    survey = csv_text(["synthetic_response_id", "usefulness_1_to_5", "verification_effort_1_to_5"], [
        [i + 1, 2 + i % 4, 1 + i * 3 % 5] for i in range(24)
    ])
    for filename, content in {
        "computational-electricity-synthetic.csv": electricity,
        "computational-negative-control-synthetic.csv": negative,
        "human-survey-synthetic.csv": survey,
    }.items():
        write(filename, content)
    for kind, question in QUESTIONS.items():
        write(kind + "-question.txt", question + "\n")

    expected = {"scope": "Offline checks of synthetic fixtures and the fixed routine; NOT API/LLM/browser E2E acceptance.",
                "computational": {}}
    for name, content in [("electricity", electricity), ("negative_control", negative)]:
        parse_csv_dataset(content)
        result = await run_tabular_regression_isolated(content, target_column="target", feature_columns=["temperature", "occupied_hours"])
        replay = await verify_tabular_repeatability_isolated(content, result)
        if not replay[0]:
            raise AssertionError(f"Repeatability failed for {name}: {replay[1]}")
        expected["computational"][name] = {
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "manifest": result["manifest"], "metrics": result["metrics"],
            "repeatability_passed": replay[0],
        }
    if expected["computational"]["negative_control"]["metrics"]["comparison"]["verdict"] != "NO_IMPROVEMENT":
        raise AssertionError("Negative control unexpectedly claims improvement")

    intake = validate_fieldwork_result("human-survey-synthetic.csv", survey.encode())
    columns = intake["csv_descriptive_statistics"]["columns"]
    expected["human"] = {"sha256": intake["sha256_hash"], "rows": intake["rows_count"], "statistics": columns}
    write("human-form-inputs.json", {
        "sample_size": 24,
        "method_notes": "SOFTWARE DEMONSTRATION ONLY. Twenty-four deterministic synthetic rows generated by scripts/prepare-demo.py. No real participants, recruitment, consent process or ethics approval. Descriptive cell arithmetic only; this is not a validated questionnaire or real fieldwork.",
        "results_summary": "SYNTHETIC DATA ONLY. There are 24 rows, no missing responses. Mean usefulness=3.5; sample SD=1.1420804814403216 (ddof=1). Mean verification effort=3.0; sample SD=1.4744195615489712 (ddof=1). Usefulness frequencies: 2:6, 3:6, 4:6, 5:6. Verification effort frequencies: 1:5, 2:5, 3:4, 4:5, 5:5. No inferential tests or causal conclusions. Check these against the uploaded CSV statistics.",
        "data_provenance": "Synthetic fixture generated by scripts/prepare-demo.py, supplied by the presenter solely to demonstrate upload, checkpoint resume and descriptive reporting. Not collected from university students. File checksum and computed statistics are in examples/demo/expected-checks.json.",
    })

    cases = {}
    for kind, research_type in [("review", "REVIEW"), ("computational", "EMPIRICAL_COMPUTATIONAL"), ("human", "EMPIRICAL_HUMAN")]:
        cases[kind] = {
            "title": {"review": "Spaced Practice and Delayed Retention: A Critical Narrative Review",
                      "computational": "Synthetic Electricity Demand: Ridge Regression versus a Mean Baseline",
                      "human": "AI Research Assistants: A Synthetic Descriptive Survey Demonstration"}[kind],
            "research_question": QUESTIONS[kind], "research_type": research_type,
            "research_depth": "STANDARD", "report_length": "MEDIUM", "language": "en",
            "citation_style": "APA" if kind != "computational" else "IEEE",
            "require_plan_approval": kind == "review", "max_sources": 12, "max_iterations": 2,
        }
    write("task-payloads.json", cases)
    write("expected-checks.json", expected)
    print("PASS: created three demo cases; ran the actual fixed routine and repeatability for two CSVs; validated survey intake.")
    print("No network/provider/database calls. See examples/demo and docs/technical/demo-guide.md.")


if __name__ == "__main__":
    asyncio.run(prepare())
