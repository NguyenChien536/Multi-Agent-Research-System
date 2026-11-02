"""python -m app.evaluation: offline protocol, collection and manual scoring."""
import argparse
import json
import sys
from pathlib import Path

from app.evaluation.protocol import freeze, record, blind, score, summarize, write_new, Specification, Run, Grade
from app.services.manuscript import REVIEW_OUTPUT_CONTRACT


def initialize(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    source = "Fictional study Alpha observed scores 2 and 3 in one controlled setting. These are synthetic fixture observations, not findings from actual research."
    (root / "source.txt").write_text(source, encoding="utf-8")
    spec = {"mode": "smoke", "code_revision": "0" * 40,
        "controls": {"model": "SET_BEFORE_REAL_EVALUATION", "model_revision": "unavailable", "temperature": 0.2,
            "language": "en", "output_contract": REVIEW_OUTPUT_CONTRACT, "retrieval_profile": "frozen-corpus-required",
            "max_llm_calls": 40, "max_input_tokens": 100000, "max_output_tokens": 50000,
            "max_cost_usd": 1.0, "timeout_seconds": 900},
        "sources": [{"id": "alpha", "path": "source.txt", "origin": "synthetic", "url": "fixture:alpha",
                     "rights_note": "Project-authored synthetic smoke fixture; not scientific evidence."}],
        "cases": [{"id": "smoke-1", "split": "pilot", "topic": "synthetic-smoke-only",
            "question": "What can the fictional Alpha observations support, and what remains uncertain?",
            "source_ids": ["alpha"], "expected_points": [{"id": "observations",
                "description": "Identify both fictional observations and their limited setting.", "source_ids": ["alpha"]}]}]}
    (root / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"specification": str(root / "spec.json"), "mode": "smoke", "provider_calls": 0,
            "notice": "Template only. Real pilot/study requires actual source snapshots, questions, rubric and pinned controls."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init"); init.add_argument("directory")
    schema = commands.add_parser("schema"); schema.add_argument("kind", choices=("spec", "run", "grade"))
    frozen = commands.add_parser("freeze"); frozen.add_argument("specification"); frozen.add_argument("output")
    run = commands.add_parser("record"); run.add_argument("bundle"); run.add_argument("metadata")
    packet = commands.add_parser("blind"); packet.add_argument("bundle"); packet.add_argument("output")
    packet.add_argument("--split", choices=("pilot", "held_out"), default="pilot")
    grade = commands.add_parser("score"); grade.add_argument("bundle"); grade.add_argument("packet"); grade.add_argument("grades")
    summary = commands.add_parser("summarize"); summary.add_argument("bundle"); summary.add_argument("packet"); summary.add_argument("output")
    args = parser.parse_args(argv)
    try:
        if args.command == "schema":
            result = {"spec": Specification, "run": Run, "grade": Grade}[args.kind].model_json_schema()
        elif args.command == "init":
            result = initialize(args.directory)
        elif args.command == "freeze":
            result = {"protocol_digest": freeze(args.specification, args.output)}
        elif args.command == "record":
            result = {"record_digest": record(args.bundle, args.metadata)}
        elif args.command == "blind":
            result = {"packet_id": blind(args.bundle, args.output, args.split)}
        elif args.command == "score":
            result = {"grades_recorded": score(args.bundle, args.packet, args.grades)}
        else:
            result = summarize(args.bundle, args.packet)
            write_new(Path(args.output), result)
            result = {"summary": str(args.output), "all_planned_cells_graded": result["all_planned_cells_graded"],
                      "mode": result["mode"], "provider_calls": 0}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
