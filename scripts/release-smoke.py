"""Exercise a running stack through HTTP, without importing backend internals.

Default: no provider calls. --generate runs ONE bounded real-provider study.
Credentials, manuscript and archives stay in the explicitly selected local output directory.
"""
import argparse
import base64
import io
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid
import zipfile


def run(args):
    base = args.url.rstrip("/")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    evidence = {"url": base, "started_at": time.time(), "checks": [], "generation_requested": args.generate}

    def request(path, method="GET", body=None, token=None, expect=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                code, data = response.status, response.read()
        except urllib.error.HTTPError as exc:
            code, data = exc.code, exc.read()
        assert code == expect, f"{method} {path}: HTTP {code}, expected {expect}"
        if not data:
            return None
        try:
            return json.loads(data)
        except (ValueError, UnicodeError):
            return data

    def check(name):
        evidence["checks"].append(name)
        (output / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(f"PASS: {name}", flush=True)

    request("/")
    assert request("/api/v1/ready")["status"] == "ready"
    request("/api/v1/research", expect=401)
    check("same-origin web, dependency readiness and authentication")
    suffix = uuid.uuid4().hex[:10]
    account = {"username": "release_" + suffix, "email": f"release_{suffix}@example.com", "password": uuid.uuid4().hex + "Aa1!"}
    request("/api/v1/auth/register", "POST", account, expect=201)
    token = request("/api/v1/auth/login", "POST", {k: account[k] for k in ("email", "password")})["access_token"]
    (output / "account.json").write_text(json.dumps(account, indent=2), encoding="utf-8")
    me = request("/api/v1/auth/me", token=token)
    assert me["email"] == account["email"]
    assert request("/api/v1/research", token=token) == []
    check("register, login and persisted profile")
    questions = {
        "REVIEW": "Under what conditions does retrieval-augmented generation reduce factual errors compared with language-model-only answering? Review published evidence from 2020 to 2026, distinguish citation correctness from factual support, and report conflicting findings and evaluation limitations.",
        "EMPIRICAL_COMPUTATIONAL": "On the supplied synthetic numeric CSV, how does the supported tabular_regression_v1 Ridge routine compare with its mean-prediction baseline under a fixed held-out split? Report actual MAE and RMSE, uncertainty and limits; do not generalize beyond this demonstration dataset.",
        "EMPIRICAL_HUMAN": "How could a small exploratory survey examine students' perceived usefulness and limitations of AI research assistants? Prepare a feasible protocol, informed-consent guidance and descriptive analysis plan, then wait for user-provided data. Do not invent participants, ethics approval or findings.",
    }
    tasks = {}
    for kind, question in questions.items():
        tasks[kind] = request("/api/v1/research", "POST", {
            "title": "Release verification: " + kind,
            "research_question": question, "research_type": kind, "language": "en",
            "research_depth": "SHALLOW", "report_length": "MEDIUM", "max_iterations": 1,
            "max_sources": 6, "citation_style": "IEEE", "require_plan_approval": False,
            "budget": {"max_cost_usd": 0.5, "max_llm_calls": 25, "max_input_tokens": 100000,
                       "max_output_tokens": 40000, "timeout_seconds": 900},
        }, token, 201)
        request(f"/api/v1/research/{tasks[kind]['id']}/monitor", token=token)
    evidence["task_ids"] = {k: v["id"] for k, v in tasks.items()}
    assert len(request("/api/v1/research", token=token)) == 3
    check("three study modes, workspace persistence and monitor")
    # Another user must never see a task or its monitor, even with a valid token.
    other = {**account, "username": "other_" + suffix, "email": "other_" + suffix + "@example.com"}
    request("/api/v1/auth/register", "POST", other, expect=201)
    other_token = request("/api/v1/auth/login", "POST", {k: other[k] for k in ("email", "password")})["access_token"]
    task_id = tasks["REVIEW"]["id"]
    for path in (f"/research/{task_id}", f"/research/{task_id}/monitor", f"/research/{task_id}/report"):
        request("/api/v1" + path, token=other_token, expect=404)
    check("cross-user task, report and monitor isolation")
    if not args.generate:
        evidence["runtime_passed"] = True
        check("non-generating release smoke complete; no provider calls")
        return
    task_id = tasks[args.generate]["id"]
    request(f"/api/v1/research/{task_id}/start", "POST", token=token, expect=202)
    evidence["generated_task_id"] = task_id
    deadline = time.monotonic() + args.timeout
    last = None
    while time.monotonic() < deadline:
        state = request(f"/api/v1/research/{task_id}", token=token)
        progress = (state["status"], state.get("current_step"))
        if progress != last:
            print("PROGRESS:", *progress, flush=True)
            last = progress
        if state["status"] in {"COMPLETED", "PARTIAL", "NEEDS_REVIEW", "FAILED", "CANCELLED", "WAITING_USER_DATA", "AWAITING_APPROVAL"}:
            break
        time.sleep(4)
    else:
        raise TimeoutError("Generation did not reach a terminal or human checkpoint within its time cap")
    evidence["final_state"] = {k: state.get(k) for k in ("id", "status", "current_step", "total_cost_usd", "total_tokens_used")}
    monitor = request(f"/api/v1/research/{task_id}/monitor", token=token)
    (output / "monitor.json").write_text(json.dumps(monitor, indent=2), encoding="utf-8")
    assert state["status"] not in {"FAILED", "CANCELLED"}, "Workflow failed; inspect private monitor and worker log"
    if state["status"] == "WAITING_USER_DATA":
        protocol = request(f"/api/v1/research/{task_id}/protocol", token=token)
        assert protocol.get("content_markdown"), "Human checkpoint must have a persisted protocol"
        (output / "protocol.md").write_text(protocol["content_markdown"], encoding="utf-8")
        evidence["runtime_passed"] = True
        evidence["scientific_quality_gate"] = "awaiting_user_data"
        check("real-provider workflow persisted a protocol and released the worker")
        return
    report = request(f"/api/v1/research/{task_id}/report", token=token)
    assert report["research_task_id"] == task_id and report["word_count"] > 0
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "report.md").write_text(report["content_markdown"], encoding="utf-8")
    version = report.get("version_number") or 1
    for template in ("IEEE_CONFERENCE", "ACM_SIGCONF"):
        bundle = request(f"/api/v1/research/{task_id}/report/versions/{version}/publication?template={template}", token=token)
        data = base64.b64decode(bundle["archive_base64"], validate=True)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.testzip() is None and any(name.endswith(".tex") for name in archive.namelist())
        (output / f"{template}.zip").write_bytes(data)
    evidence["runtime_passed"] = True
    evidence["scientific_quality_gate"] = state["status"]
    evidence["word_count"] = report["word_count"]
    check("real broker/worker/provider generation and both publication archives")
    print("Scientific status:", state["status"], "(runtime success is not scientific validation)", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:3080")
    parser.add_argument("--output", default="scratch/release-local/smoke")
    parser.add_argument("--generate", choices=("REVIEW", "EMPIRICAL_COMPUTATIONAL", "EMPIRICAL_HUMAN"))
    parser.add_argument("--timeout", type=int, default=960)
    run(parser.parse_args())
