"""Plan one A/B/C slot by default; --execute explicitly permits provider calls."""
import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from app.evaluation.protocol import ARMS, Controls, case_for, digest, protocol
from app.evaluation.corpus import RETRIEVAL_PROFILE
from app.evaluation.execution_budget import Campaign


def code_fingerprint():
    root = Path(__file__).resolve().parents[1]
    code = [(p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest())
            for p in sorted(root.rglob("*.py"))]
    return digest(code)


def attest_revision(frozen):
    expected = frozen["code_revision"]
    if frozen.get("executor_code_sha256") != code_fingerprint():
        raise ValueError("Freeze the current executor code fingerprint before permitting real calls")
    try:
        cwd = Path(__file__).resolve().parents[3]
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "backend/app"], cwd=cwd, text=True).strip()
        if dirty or head != expected:
            raise ValueError("Executor backend must match its clean frozen Git revision")
    except (OSError, subprocess.CalledProcessError):
        # Container image must carry its commit attestation; the complete source
        # fingerprint above is still checked, not trusted from this environment.
        if os.environ.get("EVALUATION_CODE_REVISION") != expected:
            raise ValueError("Container requires EVALUATION_CODE_REVISION matching the frozen commit") from None


class OpenAITransport:
    """Pinned OpenAI chat client, no cache, retries, fallback or remote retrieval."""
    def __init__(self, controls):
        from app.core.config import settings
        from langchain_openai import ChatOpenAI
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("your_"):
            raise ValueError("An OpenAI key is required for this explicit transport")
        self.client = ChatOpenAI(model=controls["model"], temperature=controls["temperature"],
            api_key=settings.OPENAI_API_KEY, max_retries=0, cache=False,
            timeout=controls["timeout_seconds"])

    async def request(self, messages, schema, outputs):
        client = self.client.model_copy(update={"max_tokens": outputs})
        if schema:
            result = await client.with_structured_output(schema, method="function_calling", include_raw=True).ainvoke(messages)
            return result["raw"], result.get("parsed")
        raw = await client.ainvoke(messages)
        return raw, raw


async def run(args, frozen):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.core.config import settings
    from app.evaluation.executor import claim_database, execute_slot, isolated_database_url
    attest_revision(frozen)
    database = os.environ.get(args.db_env)
    if not database:
        raise ValueError("Set the explicit evaluation database environment variable first")
    url = isolated_database_url(database, settings.DATABASE_URL)
    client = OpenAITransport(frozen["controls"])
    engine = create_async_engine(url, echo=False)
    try:
        await claim_database(engine, digest(frozen))
        with Campaign(Path(args.bundle) / "campaign", digest(frozen), args.campaign_cap,
                      args.input_rate, args.output_rate) as campaign:
            return await execute_slot(args.bundle, args.case, args.arm, args.attempt,
                sessions=async_sessionmaker(engine, expire_on_commit=False), client=client, campaign=campaign)
    finally:
        await engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("--case", required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--attempt", type=int, choices=range(1, 21), default=1)
    parser.add_argument("--campaign-cap", type=float, required=True, help="Total USD ceiling shared across all invocations in this bundle")
    parser.add_argument("--input-rate", type=float, required=True, help="Conservative USD/million input-token ceiling; review current provider pricing")
    parser.add_argument("--output-rate", type=float, required=True, help="Conservative USD/million output-token ceiling; include billable reasoning")
    parser.add_argument("--db-env", default="EVALUATION_DATABASE_URL")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        frozen = protocol(args.bundle)
        Controls.model_validate(frozen["controls"])
        case = case_for(frozen, args.case)
        if frozen["controls"]["retrieval_profile"] != RETRIEVAL_PROFILE or frozen["controls"]["output_contract"] != "REVIEW-v3":
            raise ValueError("This executor requires REVIEW-v3 and " + RETRIEVAL_PROFILE)
        # Validate prices even when planning. No directories/provider clients/DB
        # are opened in dry-plan mode.
        Campaign(Path(args.bundle) / "campaign", digest(frozen), args.campaign_cap, args.input_rate, args.output_rate)
        if not args.execute:
            result = {"action": "PLAN_ONLY", "case_id": args.case, "arm": args.arm, "attempt": args.attempt,
                "split": case["split"], "source_count": len(case["source_ids"]), "controls": frozen["controls"],
                "campaign_ceiling_usd": args.campaign_cap, "current_executor_sha256": code_fingerprint(),
                "source_network_calls": 0, "provider_calls": 0,
                "next": "Review and freeze controls/code; migrate a separate eval DB; add --execute for this one slot only."}
        else:
            if frozen["mode"] == "smoke":
                raise ValueError("Synthetic smoke uses fixture providers in tests; do not spend real calls on it")
            if not re.fullmatch(r"[a-f0-9]{40}", frozen["code_revision"]):
                raise ValueError("Invalid frozen revision")
            result = asyncio.run(run(args, frozen))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Provider/SQL exceptions may include secrets or SQL parameters: report
        # detailed explanations only for our own preflight validation errors.
        detail = str(exc) if isinstance(exc, (ValueError, FileExistsError)) else "Execution failed; inspect the private run record and service logs."
        print(json.dumps({"error": type(exc).__name__, "detail": detail}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
