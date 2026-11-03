"""Offline evaluation preparation/collection. Never invokes an agent or provider."""
import hashlib
import json
import random
import re
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ARMS = ("single_agent", "multi_agent", "no_macro_loop")
DELIVERED = {"COMPLETED", "NEEDS_REVIEW", "PARTIAL"}
ID = r"^[a-z0-9][a-z0-9_-]{0,63}$"
SHA = r"^[a-f0-9]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Controls(StrictModel):
    provider: Literal["openai", "gemini"] = "openai"
    model: str = Field(min_length=1, max_length=150)
    model_revision: str = Field(min_length=1, max_length=150)
    temperature: float | None = Field(ge=0, le=2)
    sampling_mode: Literal["temperature", "provider_default"] = "temperature"
    language: str = Field(min_length=2, max_length=10)
    output_contract: str = Field(min_length=1, max_length=150)
    retrieval_profile: str = Field(min_length=1, max_length=150)
    max_llm_calls: int = Field(ge=1, le=40)
    max_input_tokens: int = Field(ge=1, le=100000)
    max_output_tokens: int = Field(ge=1, le=50000)
    max_cost_usd: float = Field(gt=0, le=2)
    timeout_seconds: int = Field(ge=1, le=900)

    @model_validator(mode="after")
    def sampling_matches_declaration(self):
        if (self.sampling_mode == "temperature") != (self.temperature is not None):
            raise ValueError("Temperature mode requires a value; provider_default requires null temperature")
        return self


class Source(StrictModel):
    id: str = Field(pattern=ID)
    path: str
    origin: Literal["primary", "user_provided", "synthetic"]
    url: str = Field(min_length=1, max_length=2000)
    rights_note: str = Field(min_length=5, max_length=1000)


class ExpectedPoint(StrictModel):
    id: str = Field(pattern=ID)
    description: str = Field(min_length=10, max_length=2000)
    source_ids: list[str] = Field(min_length=1, max_length=20)


class Case(StrictModel):
    id: str = Field(pattern=ID)
    split: Literal["pilot", "held_out"]
    topic: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=10, max_length=3000)
    source_ids: list[str] = Field(min_length=1, max_length=20)
    expected_points: list[ExpectedPoint] = Field(min_length=1, max_length=30)


class Specification(StrictModel):
    mode: Literal["smoke", "pilot", "study"]
    code_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    executor_code_sha256: str | None = Field(default=None, pattern=SHA)
    controls: Controls
    sources: list[Source] = Field(min_length=1, max_length=50)
    cases: list[Case] = Field(min_length=1, max_length=12)


class Run(StrictModel):
    protocol_digest: str = Field(pattern=SHA)
    case_id: str = Field(pattern=ID)
    arm: Literal["single_agent", "multi_agent", "no_macro_loop"]
    attempt: int = Field(ge=1, le=20)
    status: Literal["COMPLETED", "NEEDS_REVIEW", "PARTIAL", "FAILED", "TIMEOUT", "BUDGET_EXCEEDED"]
    observed_controls: Controls
    code_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    used_source_ids: list[str] = Field(max_length=50)
    macro_loop_enabled: bool
    micro_revision_enabled: bool
    network_calls: int = Field(ge=0)
    llm_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    active_seconds: float = Field(ge=0)
    report_path: str | None = None
    trace_path: str
    error: str | None = Field(default=None, max_length=2000)
    execution_control_violations: list[str] = Field(default_factory=list, max_length=20)


class EvidenceQuote(StrictModel):
    source_id: str
    quote: str = Field(min_length=1, max_length=3000)


class ClaimJudgment(StrictModel):
    report_quote: str = Field(min_length=1, max_length=3000)
    judgment: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED", "CONTRADICTED", "UNVERIFIABLE"]
    evidence: list[EvidenceQuote] = Field(max_length=10)
    reason: str = Field(min_length=5, max_length=2000)


class PointJudgment(StrictModel):
    point_id: str
    covered_with_support: bool
    evidence: list[EvidenceQuote] = Field(max_length=10)
    reason: str = Field(min_length=5, max_length=2000)


class Grade(StrictModel):
    blind_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    reviewer: str = Field(min_length=1, max_length=100)
    evaluator_type: Literal["HUMAN", "LLM_ASSISTED_HUMAN"]
    controls_reviewed: bool
    claims: list[ClaimJudgment] = Field(max_length=5)
    reduced_sample_reason: str | None = Field(default=None, min_length=10, max_length=1000)
    points: list[PointJudgment] = Field(min_length=1, max_length=30)
    limitations: int = Field(ge=0, le=2)
    gap_quality: int = Field(ge=0, le=2)
    fabricated_results: int = Field(ge=0)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read_bytes(path, limit):
    with Path(path).open("rb") as handle:
        content = handle.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Evaluation input exceeds its size limit")
    return content


def read_json(path):
    return json.loads(read_bytes(path, 25 * 1024 * 1024).decode("utf-8"))


def write_new(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {"sha256": digest(payload), "payload": payload}
    with path.open("xb") as handle:
        handle.write(encoded(envelope))
    return envelope["sha256"]


def checked(path):
    envelope = read_json(path)
    if set(envelope) != {"sha256", "payload"} or digest(envelope["payload"]) != envelope["sha256"]:
        raise ValueError("Evaluation artifact checksum mismatch")
    return envelope["payload"]


def unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")


def freeze(spec_path, output):
    spec_path, output = Path(spec_path).resolve(), Path(output).resolve()
    spec = Specification.model_validate(read_json(spec_path))
    unique([s.id for s in spec.sources], "source identity")
    unique([c.id for c in spec.cases], "case identity")
    unique([" ".join(c.question.casefold().split()) for c in spec.cases], "question across pilot/held-out")
    sources = {}
    total = 0
    for source in spec.sources:
        path = (spec_path.parent / source.path).resolve()
        if not path.is_relative_to(spec_path.parent) or path == spec_path:
            raise ValueError("Source files must remain within the specification directory")
        text = read_bytes(path, 1_000_000).decode("utf-8")
        if not text.strip():
            raise ValueError("Empty source text")
        total += len(text.encode())
        if total > 20_000_000:
            raise ValueError("Corpus exceeds its size limit")
        sources[source.id] = {**source.model_dump(exclude={"path"}), "text": text,
                              "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    for case in spec.cases:
        unique(case.source_ids, "case source")
        unique([p.id for p in case.expected_points], "expected point")
        if not set(case.source_ids) <= sources.keys():
            raise ValueError("Case refers to an unknown source")
        for point in case.expected_points:
            if not set(point.source_ids) <= set(case.source_ids):
                raise ValueError("Expected point refers outside its case corpus")
    counts = {split: sum(c.split == split for c in spec.cases) for split in ("pilot", "held_out")}
    if spec.mode == "study" and counts != {"pilot": 4, "held_out": 8}:
        raise ValueError("A study requires four pilot and eight held-out cases")
    if spec.mode == "study" and not 2 <= len({c.topic for c in spec.cases if c.split == "held_out"}) <= 3:
        raise ValueError("Held-out cases must span two or three topics")
    if spec.mode == "pilot" and counts != {"pilot": 4, "held_out": 0}:
        raise ValueError("A pilot requires four pilot cases without held-out cases")
    if spec.mode != "smoke" and any(s.origin == "synthetic" for s in spec.sources):
        raise ValueError("Synthetic smoke sources cannot be presented as a real evaluation corpus")
    if spec.mode != "smoke" and (spec.code_revision == "0" * 40 or spec.controls.model.startswith("SET_")
                                  or spec.controls.retrieval_profile.endswith("required")):
        raise ValueError("Replace template implementation/model/retrieval controls before a real evaluation")
    payload = {**spec.model_dump(exclude={"sources"}), "schema_version": 1,
               "sources": sources, "arms": list(ARMS), "primary_attempt": 1,
               "frozen_at": datetime.now(timezone.utc).isoformat()}
    if len(encoded(payload)) > 24_000_000:
        raise ValueError("Serialized protocol exceeds its size limit")
    output.mkdir(parents=True, exist_ok=False)
    return write_new(output / "protocol.json", payload)


def protocol(root):
    return checked(Path(root) / "protocol.json")


def case_for(frozen, case_id):
    case = next((c for c in frozen["cases"] if c["id"] == case_id), None)
    if not case:
        raise ValueError("Unknown evaluation case")
    return case


def run_key(case_id, arm, attempt=1):
    return f"{case_id}--{arm}--{attempt:02d}"


def record(root, metadata_path):
    root, metadata_path = Path(root), Path(metadata_path).resolve()
    frozen = protocol(root)
    run = Run.model_validate(read_json(metadata_path))
    if run.protocol_digest != digest(frozen):
        raise ValueError("Run does not belong to this frozen protocol")
    case = case_for(frozen, run.case_id)
    def input_file(name):
        path = (metadata_path.parent / name).resolve()
        if not path.is_relative_to(metadata_path.parent):
            raise ValueError("Run inputs must remain within the metadata directory")
        return read_bytes(path, 2_000_000).decode("utf-8")
    report = input_file(run.report_path) if run.report_path else ""
    trace = json.loads(input_file(run.trace_path))
    if run.status in DELIVERED and not report.strip():
        raise ValueError("Delivered run requires a manuscript")
    violations = list(run.execution_control_violations)
    expected = frozen["controls"]
    if run.observed_controls.model_dump() != expected:
        violations.append("model/revision/temperature/output/retrieval/caps differ")
    if run.code_revision != frozen["code_revision"]:
        violations.append("implementation revision differs")
    if run.network_calls:
        violations.append("live network calls reported")
    if not set(run.used_source_ids) <= set(case["source_ids"]):
        violations.append("sources outside the case corpus")
    if run.macro_loop_enabled != (run.arm == "multi_agent") or run.micro_revision_enabled != (run.arm != "single_agent"):
        violations.append("loop configuration differs from the registered arm")
    for usage, cap in (("llm_calls", "max_llm_calls"), ("input_tokens", "max_input_tokens"),
                       ("output_tokens", "max_output_tokens"), ("estimated_cost_usd", "max_cost_usd"),
                       ("active_seconds", "timeout_seconds")):
        if getattr(run, usage) > expected[cap]:
            violations.append(f"reported {usage} exceeds cap")
    payload = {**run.model_dump(exclude={"report_path", "trace_path"}), "report": report, "trace": trace,
               "reported_control_violations": violations, "eligible": not violations and run.status in DELIVERED,
               "control_evidence": "imported metadata and trace; requires reviewer confirmation, not runtime enforcement"}
    return write_new(root / "runs" / f"{run_key(run.case_id, run.arm, run.attempt)}.json", payload)


def load_runs(root, frozen):
    result = {}
    for path in sorted((Path(root) / "runs").glob("*.json")):
        run = checked(path)
        model = Run.model_validate({**{k: v for k, v in run.items() if k in Run.model_fields}, "trace_path": "frozen-trace.json"})
        case_for(frozen, model.case_id)
        key = run_key(model.case_id, model.arm, model.attempt)
        if model.protocol_digest != digest(frozen) or path.stem != key or key in result:
            raise ValueError("Run identity/protocol mismatch")
        result[key] = run
    return result


def blind(root, packet_dir, split="pilot"):
    root, packet_dir = Path(root), Path(packet_dir)
    frozen = protocol(root)
    runs = load_runs(root, frozen)
    if split not in {"pilot", "held_out"}:
        raise ValueError("Invalid evaluation split")
    primary_path = root / "blindings" / f"primary-{split}.json"
    if primary_path.exists():
        raise FileExistsError("This split already has its primary blind packet; do not reblind to replace grades")
    cases = [case for case in frozen["cases"] if case["split"] == split]
    if not cases:
        raise ValueError("The requested split has no cases")
    mapping, reports = {}, []
    for case in cases:
        for arm in ARMS:
            key, blind_id = run_key(case["id"], arm), uuid.uuid4().hex
            run = runs.get(key)
            mapping[blind_id] = {"key": key, "case_id": case["id"], "arm": arm,
                                 "run_digest": digest(run) if run else None}
            reports.append({"blind_id": blind_id, "case_id": case["id"], "report": run["report"] if run else "",
                            "status": ("DELIVERED" if run["status"] in DELIVERED else run["status"]) if run else "MISSING",
                            "eligible": bool(run and run["eligible"])})
    random.SystemRandom().shuffle(reports)
    packet_id = uuid.uuid4().hex
    source_ids = {sid for case in cases for sid in case["source_ids"]}
    packet = {"packet_id": packet_id, "split": split, "protocol_digest": digest(frozen), "cases": cases,
              "sources": {sid: value for sid, value in frozen["sources"].items() if sid in source_ids}, "reports": reports,
              "blinding_limit": "Only arm/control/trace metadata is concealed; manuscript wording may reveal the method."}
    packet_dir.mkdir(parents=True, exist_ok=False)
    write_new(packet_dir / "packet.json", packet)
    write_new(root / "blindings" / f"{packet_id}.json", {"protocol_digest": digest(frozen), "mapping": mapping,
                                                       "packet_digest": digest(packet)})
    write_new(primary_path, {"packet_id": packet_id, "protocol_digest": digest(frozen)})
    return packet_id


def packet_context(root, packet_dir):
    frozen = protocol(root)
    packet = checked(Path(packet_dir) / "packet.json")
    if not re.fullmatch(r"[a-f0-9]{32}", packet.get("packet_id", "")):
        raise ValueError("Invalid packet identity")
    if packet.get("split") not in {"pilot", "held_out"}:
        raise ValueError("Invalid packet split")
    key = checked(Path(root) / "blindings" / f"{packet['packet_id']}.json")
    primary = checked(Path(root) / "blindings" / f"primary-{packet['split']}.json")
    if primary != {"packet_id": packet["packet_id"], "protocol_digest": digest(frozen)}:
        raise ValueError("This is not the registered primary blind packet")
    if (packet["protocol_digest"] != digest(frozen) or key["protocol_digest"] != digest(frozen)
            or key["packet_digest"] != digest(packet)):
        raise ValueError("Blind packet/protocol mismatch")
    runs = load_runs(root, frozen)
    for mapping in key["mapping"].values():
        run = runs.get(mapping["key"])
        if (digest(run) if run else None) != mapping["run_digest"]:
            raise ValueError("Runs changed after blinding; a revised protocol is required, preserving the original")
    return frozen, packet, key, runs


def check_evidence(evidence, case, frozen, required):
    if required and not evidence:
        raise ValueError("Supported judgment requires quoted source evidence")
    for item in evidence:
        if item.source_id not in case["source_ids"] or item.quote not in frozen["sources"][item.source_id]["text"]:
            raise ValueError("Reviewer evidence is absent from the frozen case corpus")


def score(root, packet_dir, grades_path):
    frozen, packet, key, runs = packet_context(root, packet_dir)
    inputs = read_json(grades_path)
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 36:
        raise ValueError("Provide between one and 36 report grades")
    grades = [Grade.model_validate(item) for item in inputs]
    unique([g.blind_id for g in grades], "blind grade")
    prepared = []
    for grade in grades:
        mapping = key["mapping"].get(grade.blind_id)
        run = runs.get(mapping["key"]) if mapping else None
        if not run or not run["eligible"] or not grade.controls_reviewed:
            raise ValueError("Only eligible completed runs with reviewed controls may receive a grade")
        case = case_for(frozen, run["case_id"])
        if len(grade.claims) < 5 and not grade.reduced_sample_reason:
            raise ValueError("Fewer than five sampled claims requires an explanation")
        unique([c.report_quote for c in grade.claims], "sampled claim")
        for claim in grade.claims:
            if claim.report_quote not in run["report"]:
                raise ValueError("Sampled claim is absent from the manuscript")
            check_evidence(claim.evidence, case, frozen, claim.judgment == "SUPPORTED")
        expected_ids = {p["id"] for p in case["expected_points"]}
        if len(grade.points) != len(expected_ids) or {p.point_id for p in grade.points} != expected_ids:
            raise ValueError("Grade must cover every expected point exactly once")
        for point in grade.points:
            check_evidence(point.evidence, case, frozen, point.covered_with_support)
        payload = {"packet_id": packet["packet_id"], "run_digest": digest(run), "grade": grade.model_dump(),
                   "semantic_support": "reviewer judgment; quote existence alone does not prove entailment"}
        path = Path(root) / "grades" / f"{packet['packet_id']}--{grade.blind_id}.json"
        if path.exists():
            raise FileExistsError("A grade already exists; preserve it and create a new evaluation protocol for changed rubrics")
        prepared.append((path, payload))
    for path, payload in prepared:
        write_new(path, payload)
    return len(prepared)


def summarize(root, packet_dir):
    frozen, packet, key, runs = packet_context(root, packet_dir)
    rows = []
    for blind_id, mapping in key["mapping"].items():
        run = runs.get(mapping["key"])
        case_id, arm = mapping["case_id"], mapping["arm"]
        case = case_for(frozen, case_id)
        path = Path(root) / "grades" / f"{packet['packet_id']}--{blind_id}.json"
        grade = None
        if path.exists():
            stored = checked(path)
            if not run or stored["run_digest"] != digest(run) or stored["packet_id"] != packet["packet_id"]:
                raise ValueError("Grade refers to a different run or packet")
            grade = Grade.model_validate(stored["grade"])
            if grade.blind_id != blind_id:
                raise ValueError("Grade identity does not match its artifact")
        rows.append({"case_id": case_id, "split": case["split"], "arm": arm,
            "status": run["status"] if run else "MISSING", "eligible": bool(run and run["eligible"]),
            "graded": grade is not None,
            "support": sum(c.judgment == "SUPPORTED" for c in grade.claims) / len(grade.claims) if grade and grade.claims else None,
            "sampled_claim_count": len(grade.claims) if grade else None,
            "coverage": sum(p.covered_with_support for p in grade.points) / len(grade.points) if grade else None,
            "limitations": grade.limitations if grade else None, "gap_quality": grade.gap_quality if grade else None,
            "fabricated_results": grade.fabricated_results if grade else None,
            "estimated_cost_usd": run["estimated_cost_usd"] if run else None,
            "active_seconds": run["active_seconds"] if run else None,
            "control_violations": run["reported_control_violations"] if run else []})
    groups, pairs = [], []
    selected_cases = packet["cases"]
    for split in ("pilot", "held_out"):
        if not any(c["split"] == split for c in selected_cases):
            continue
        for arm in ARMS:
            selected = [r for r in rows if r["split"] == split and r["arm"] == arm]
            if not selected:
                continue
            graded = [r for r in selected if r["eligible"] and r["graded"]]
            support_scored = [r for r in graded if r["support"] is not None]
            durations = [r["active_seconds"] for r in selected if r["active_seconds"] is not None]
            groups.append({"split": split, "arm": arm, "planned": len(selected),
                "missing": sum(r["status"] == "MISSING" for r in selected),
                "noncompleted": sum(r["status"] not in DELIVERED | {"MISSING"} for r in selected),
                "delivered": sum(r["status"] in DELIVERED for r in selected),
                "needs_review": sum(r["status"] == "NEEDS_REVIEW" for r in selected),
                "partial": sum(r["status"] == "PARTIAL" for r in selected),
                "control_invalid": sum(bool(r["control_violations"]) for r in selected), "graded": len(graded),
                "eligible_ungraded": sum(r["eligible"] and not r["graded"] for r in selected),
                "total_estimated_cost_usd": sum(r["estimated_cost_usd"] for r in selected if r["estimated_cost_usd"] is not None),
                "active_seconds_median": statistics.median(durations) if durations else None,
                "active_seconds_range": [min(durations), max(durations)] if durations else None,
                "support_scored_reports": len(support_scored),
                "mean_support": sum(r["support"] for r in support_scored) / len(support_scored) if support_scored else None,
                "pooled_sample_support": (sum(r["support"] * r["sampled_claim_count"] for r in support_scored) /
                    sum(r["sampled_claim_count"] for r in support_scored)) if support_scored else None,
                "mean_coverage": sum(r["coverage"] for r in graded) / len(graded) if graded else None,
                "fabricated_results": sum(r["fabricated_results"] for r in graded) if graded else None})
        for left, right in (("multi_agent", "single_agent"), ("multi_agent", "no_macro_loop")):
            differences = []
            for case in (c for c in selected_cases if c["split"] == split):
                a = next(r for r in rows if r["case_id"] == case["id"] and r["arm"] == left)
                b = next(r for r in rows if r["case_id"] == case["id"] and r["arm"] == right)
                if a["eligible"] and b["eligible"] and a["graded"] and b["graded"]:
                    differences.append({"case_id": case["id"], "support_delta": (a["support"] - b["support"])
                                        if a["support"] is not None and b["support"] is not None else None,
                                        "coverage_delta": a["coverage"] - b["coverage"],
                                        "estimated_cost_delta_usd": a["estimated_cost_usd"] - b["estimated_cost_usd"],
                                        "active_seconds_delta": a["active_seconds"] - b["active_seconds"]})
            pairs.append({"split": split, "comparison": f"{left} minus {right}", "paired_count": len(differences),
                          "support_paired_count": sum(d["support_delta"] is not None for d in differences),
                          "planned_pairs": sum(c["split"] == split for c in selected_cases), "differences": differences})
    complete = all(r["eligible"] and r["graded"] for r in rows)
    return {"protocol_digest": digest(frozen), "mode": frozen["mode"], "primary_attempt": 1,
            "packet_split": packet["split"], "all_packet_cells_graded": complete,
            "all_planned_cells_graded": complete and len(rows) == len(frozen["cases"]) * len(ARMS),
            "strict_fabrication_gate": all(r["fabricated_results"] == 0 for r in rows) if complete else None,
            "model_revision_fully_pinned": frozen["controls"]["model_revision"].casefold() not in {"unavailable", "unknown", "alias"},
            "groups": groups, "pairs": pairs, "rows": rows,
            "reruns_retained": sum(r["attempt"] != 1 for r in runs.values()),
            "reruns": [{k: r[k] for k in ("case_id", "arm", "attempt", "status", "eligible", "estimated_cost_usd", "active_seconds")}
                       for r in runs.values() if r["attempt"] != 1],
            "limitations": ["Imported execution controls require trace review, not merely matching metadata.",
                "Semantic labels and claim selection are manual; one reviewer cannot establish inter-rater agreement.",
                "Pilot and held-out are separate; ungraded/failed/missing outputs are not silently assigned quality scores.",
                "No superiority, statistical significance or production readiness follows from this summary alone."]}
