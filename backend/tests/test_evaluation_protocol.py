import json
from pathlib import Path

import pytest

from app.evaluation.__main__ import initialize, main
from app.evaluation.protocol import (ARMS, DELIVERED, blind, checked, digest, freeze, protocol, record, score, summarize)


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def study(tmp_path):
    source = tmp_path / "inputs"
    initialize(source)
    root = tmp_path / "frozen"
    freeze(source / "spec.json", root)
    return source, root


def add_run(source, root, arm="single_agent", attempt=1, status="COMPLETED", *, via_cli=False, **overrides):
    frozen = protocol(root)
    report_path = source / f"report-{arm}-{attempt}.md"
    report_path.write_text("# Smoke manuscript\n\nScores were 2 and 3. The evidence is a synthetic fixture.", encoding="utf-8")
    trace_path = source / f"trace-{arm}-{attempt}.json"
    write(trace_path, {"synthetic": True, "private_model": "private-provider-label", "role": arm})
    payload = {"protocol_digest": digest(frozen), "case_id": "smoke-1", "arm": arm, "attempt": attempt,
        "status": status, "observed_controls": frozen["controls"], "code_revision": frozen["code_revision"],
        "used_source_ids": ["alpha"], "macro_loop_enabled": arm == "multi_agent",
        "micro_revision_enabled": arm != "single_agent", "network_calls": 0, "llm_calls": 2,
        "input_tokens": 200, "output_tokens": 100, "estimated_cost_usd": 0.1, "active_seconds": 10.0,
        "report_path": report_path.name if status in DELIVERED else None, "trace_path": trace_path.name,
        "error": None if status == "COMPLETED" else "Controlled synthetic failure", **overrides}
    path = write(source / f"metadata-{arm}-{attempt}.json", payload)
    if via_cli:
        assert main(["record", str(root), str(path)]) == 0
    else:
        record(root, path)
    return path


def grade_for(blind_id, *, supported=True):
    evidence = [{"source_id": "alpha", "quote": "scores 2 and 3"}] if supported else []
    return {"blind_id": blind_id, "reviewer": "fixture-reviewer", "evaluator_type": "HUMAN",
        "controls_reviewed": True, "reduced_sample_reason": "Only one explicit claim occurs in this synthetic smoke manuscript.",
        "claims": [{"report_quote": "Scores were 2 and 3.", "judgment": "SUPPORTED" if supported else "UNSUPPORTED",
                    "evidence": evidence, "reason": "Controlled fixture judgment, not a scientific finding."}],
        "points": [{"point_id": "observations", "covered_with_support": supported, "evidence": evidence,
                    "reason": "Controlled fixture judgment based on the supplied source."}],
        "limitations": 1, "gap_quality": 1, "fabricated_results": 0}


def test_source_edits_after_freeze_do_not_change_the_snapshot(study):
    source, root = study
    original = protocol(root)
    (source / "source.txt").write_text("Changed source", encoding="utf-8")
    assert protocol(root) == original
    assert "Fictional study Alpha" in original["sources"]["alpha"]["text"]


@pytest.mark.parametrize("failure", ["duplicate_case", "unknown_source", "outside_file", "empty_source", "duplicate_question", "synthetic_study"])
def test_freeze_rejects_invalid_protocols(tmp_path, failure):
    inputs = tmp_path / "inputs"; initialize(inputs)
    spec = json.loads((inputs / "spec.json").read_text())
    if failure == "duplicate_case":
        spec["cases"].append(spec["cases"][0])
    elif failure == "unknown_source":
        spec["cases"][0]["source_ids"] = ["missing"]
    elif failure == "outside_file":
        (tmp_path / "outside.txt").write_text("Outside text")
        spec["sources"][0]["path"] = "../outside.txt"
    elif failure == "empty_source":
        (inputs / "source.txt").write_text(" ")
    elif failure == "duplicate_question":
        spec["cases"].append({**spec["cases"][0], "id": "another", "split": "held_out"})
    else:
        spec["mode"] = "pilot"
        spec["cases"] = [{**spec["cases"][0], "id": f"q{i}", "question": f"Distinct fictional pilot question number {i}?"} for i in range(4)]
    write(inputs / "spec.json", spec)
    with pytest.raises(ValueError):
        freeze(inputs / "spec.json", tmp_path / "output")


def test_protocol_tampering_is_detected(study):
    _, root = study
    envelope = json.loads((root / "protocol.json").read_text())
    envelope["payload"]["controls"]["max_cost_usd"] = 2.0
    write(root / "protocol.json", envelope)
    with pytest.raises(ValueError, match="checksum"):
        protocol(root)


def test_duplicate_run_and_grade_cannot_overwrite_originals(study, tmp_path):
    source, root = study
    metadata = add_run(source, root)
    with pytest.raises(FileExistsError):
        record(root, metadata)
    packet_dir = tmp_path / "packet"; pid = blind(root, packet_dir)
    key = checked(root / "blindings" / f"{pid}.json")
    bid = next(k for k, v in key["mapping"].items() if v["arm"] == "single_agent")
    grades = write(source / "grades.json", [grade_for(bid)])
    assert score(root, packet_dir, grades) == 1
    with pytest.raises(FileExistsError):
        score(root, packet_dir, grades)
    with pytest.raises(FileExistsError, match="primary"):
        blind(root, tmp_path / "replacement")


@pytest.mark.parametrize("override,violation", [
    ({"network_calls": 1}, "network"), ({"used_source_ids": ["external"]}, "sources"),
    ({"micro_revision_enabled": True}, "loop"), ({"llm_calls": 41}, "cap"),
    ({"code_revision": "a" * 40}, "revision"), ({"estimated_cost_usd": 1.01}, "cap"),
])
def test_control_violations_are_retained_instead_of_dropped(study, override, violation):
    source, root = study
    add_run(source, root, **override)
    run = checked(next((root / "runs").glob("*.json")))
    assert not run["eligible"]
    assert any(violation in v for v in run["reported_control_violations"])
    assert run["trace"]["synthetic"]


def test_failed_first_attempt_is_not_replaced_by_a_successful_rerun(study, tmp_path):
    source, root = study
    add_run(source, root, status="TIMEOUT")
    add_run(source, root, attempt=2)
    add_run(source, root, arm="multi_agent")
    packet = tmp_path / "packet"; blind(root, packet)
    result = summarize(root, packet)
    a = next(g for g in result["groups"] if g["arm"] == "single_agent")
    c = next(g for g in result["groups"] if g["arm"] == "no_macro_loop")
    assert a["noncompleted"] == 1 and a["graded"] == 0 and a["mean_support"] is None
    assert a["total_estimated_cost_usd"] == 0.1 and a["active_seconds_median"] == 10.0
    assert c["missing"] == 1
    assert result["reruns_retained"] == 1 and result["reruns"][0]["status"] == "COMPLETED"
    assert result["all_planned_cells_graded"] is False and result["strict_fabrication_gate"] is None


def test_blind_packet_hides_execution_metadata_and_keeps_key_private(study, tmp_path):
    source, root = study
    for arm in ARMS:
        add_run(source, root, arm=arm)
    packet = tmp_path / "packet"; pid = blind(root, packet)
    public = checked(packet / "packet.json")
    assert [p.name for p in packet.iterdir()] == ["packet.json"]
    assert "private-provider-label" not in json.dumps(public)
    assert "single_agent" not in json.dumps(public)
    assert "controls" not in public and "trace" not in public and "mapping" not in public
    assert (root / "blindings" / f"{pid}.json").exists()


@pytest.mark.parametrize("failure", ["claim_quote", "source_quote", "unknown_point", "duplicate_point", "missing_sample_reason", "unreviewed_controls"])
def test_invalid_manual_rubrics_are_rejected(study, tmp_path, failure):
    source, root = study
    add_run(source, root)
    packet = tmp_path / "packet"; pid = blind(root, packet)
    key = checked(root / "blindings" / f"{pid}.json")
    bid = next(k for k, v in key["mapping"].items() if v["arm"] == "single_agent")
    grade = grade_for(bid)
    if failure == "claim_quote":
        grade["claims"][0]["report_quote"] = "An invented claim."
    elif failure == "source_quote":
        grade["claims"][0]["evidence"][0]["quote"] = "This is absent from the source."
    elif failure == "unknown_point":
        grade["points"][0]["point_id"] = "invented"
    elif failure == "duplicate_point":
        grade["points"].append(grade["points"][0])
    elif failure == "missing_sample_reason":
        grade["reduced_sample_reason"] = None
    else:
        grade["controls_reviewed"] = False
    with pytest.raises(ValueError):
        score(root, packet, write(source / "grades.json", [grade]))
    assert not list((root / "grades").glob("*.json"))


def test_negative_paired_differences_are_preserved(study, tmp_path):
    source, root = study
    for arm in ARMS:
        add_run(source, root, arm=arm)
    packet = tmp_path / "packet"; pid = blind(root, packet)
    key = checked(root / "blindings" / f"{pid}.json")
    grades = [grade_for(bid, supported=item["arm"] != "multi_agent") for bid, item in key["mapping"].items()]
    assert score(root, packet, write(source / "grades.json", grades)) == 3
    result = summarize(root, packet)
    assert result["all_packet_cells_graded"] and result["strict_fabrication_gate"]
    assert all(p["paired_count"] == 1 and p["differences"][0]["support_delta"] == -1 for p in result["pairs"])
    assert result["mode"] == "smoke" and result["model_revision_fully_pinned"] is False


def test_primary_run_changes_after_blinding_require_a_revised_protocol(study, tmp_path):
    source, root = study
    packet = tmp_path / "packet"; blind(root, packet)
    add_run(source, root)
    with pytest.raises(ValueError, match="changed after blinding"):
        summarize(root, packet)


def test_pilot_packet_does_not_expose_held_out_cases_or_sources(tmp_path):
    inputs = tmp_path / "inputs"; initialize(inputs)
    spec = json.loads((inputs / "spec.json").read_text())
    (inputs / "held.txt").write_text("Private held-out corpus not part of the pilot.")
    spec["sources"].append({**spec["sources"][0], "id": "held", "path": "held.txt"})
    spec["cases"].append({**spec["cases"][0], "id": "held-1", "split": "held_out",
        "question": "What does the separate held-out source establish?", "source_ids": ["held"],
        "expected_points": [{"id": "held-point", "description": "Assess the held-out source separately.", "source_ids": ["held"]}]})
    write(inputs / "spec.json", spec)
    root = tmp_path / "root"; freeze(inputs / "spec.json", root)
    packet = tmp_path / "packet"; blind(root, packet, "pilot")
    public = checked(packet / "packet.json")
    assert len(public["reports"]) == 3 and len(public["cases"]) == 1
    assert set(public["sources"]) == {"alpha"}
    result = summarize(root, packet)
    assert all(g["split"] == "pilot" for g in result["groups"])
    assert not result["all_planned_cells_graded"]


def test_cli_offline_workflow_and_immutable_outputs(tmp_path, capsys):
    inputs, root, packet, output = [tmp_path / name for name in ("inputs", "root", "packet", "summary.json")]
    assert main(["init", str(inputs)]) == 0
    assert main(["freeze", str(inputs / "spec.json"), str(root)]) == 0
    assert main(["blind", str(root), str(packet)]) == 0
    assert main(["summarize", str(root), str(packet), str(output)]) == 0
    assert checked(output)["groups"][0]["missing"] == 1
    assert main(["summarize", str(root), str(packet), str(output)]) == 2
    assert main(["freeze", str(inputs / "spec.json"), str(root)]) == 2
    assert '"provider_calls": 0' in capsys.readouterr().out


def test_complete_cli_collection_grading_and_summary(study, tmp_path):
    source, root = study
    for arm in ARMS:
        add_run(source, root, arm=arm, via_cli=True)
    packet = tmp_path / "packet"
    assert main(["blind", str(root), str(packet), "--split", "pilot"]) == 0
    public = checked(packet / "packet.json")
    grades = write(source / "grades.json", [grade_for(r["blind_id"]) for r in public["reports"]])
    assert main(["score", str(root), str(packet), str(grades)]) == 0
    out = tmp_path / "summary.json"
    assert main(["summarize", str(root), str(packet), str(out)]) == 0
    result = checked(out)
    assert result["all_planned_cells_graded"] and len(result["rows"]) == 3
    assert all(g["pooled_sample_support"] == 1 for g in result["groups"])
    assert all(p["paired_count"] == 1 and p["differences"][0]["coverage_delta"] == 0 for p in result["pairs"])


def test_positive_fabricated_result_count_fails_the_strict_gate(study, tmp_path):
    source, root = study
    for arm in ARMS:
        add_run(source, root, arm=arm)
    packet = tmp_path / "packet"; blind(root, packet)
    public = checked(packet / "packet.json")
    grades = [grade_for(r["blind_id"]) for r in public["reports"]]
    grades[0]["fabricated_results"] = 1
    score(root, packet, write(source / "grades.json", grades))
    result = summarize(root, packet)
    assert result["all_planned_cells_graded"] and result["strict_fabrication_gate"] is False


@pytest.mark.parametrize("status", ["NEEDS_REVIEW", "PARTIAL"])
def test_delivered_drafts_are_graded_without_revealing_internal_verdict(study, tmp_path, status):
    source, root = study
    add_run(source, root, status=status)
    packet = tmp_path / "packet"; pid = blind(root, packet)
    public = checked(packet / "packet.json")
    delivered = next(r for r in public["reports"] if r["report"])
    assert delivered["status"] == "DELIVERED" and delivered["eligible"]
    score(root, packet, write(source / "grades.json", [grade_for(delivered["blind_id"])]))
    result = summarize(root, packet)
    group = next(g for g in result["groups"] if g["arm"] == "single_agent")
    assert group["graded"] == 1 and group["delivered"] == 1 and group["noncompleted"] == 0


def test_schema_command_exposes_required_controls_without_running_a_provider(capsys):
    assert main(["schema", "run"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert {"protocol_digest", "observed_controls", "trace_path", "macro_loop_enabled"} <= set(schema["required"])


def test_no_sampled_claims_is_undefined_support_not_a_perfect_or_zero_score(study, tmp_path):
    source, root = study
    for arm in ARMS:
        add_run(source, root, arm=arm)
    packet = tmp_path / "packet"; pid = blind(root, packet)
    key = checked(root / "blindings" / f"{pid}.json")
    grades = []
    for bid, item in key["mapping"].items():
        grade = grade_for(bid)
        if item["arm"] == "multi_agent":
            grade["claims"] = []
            grade["reduced_sample_reason"] = "The reviewer found no factual claims to sample in this controlled example."
        grades.append(grade)
    score(root, packet, write(source / "grades.json", grades))
    result = summarize(root, packet)
    group = next(g for g in result["groups"] if g["arm"] == "multi_agent")
    assert group["mean_support"] is None and group["pooled_sample_support"] is None
    assert group["support_scored_reports"] == 0 and group["graded"] == 1
    assert all(p["support_paired_count"] == 0 and p["differences"][0]["support_delta"] is None for p in result["pairs"])
