"""Bounded evidence and manuscript review role."""

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import HumanMessage

from app.agents.agent_schemas import CriticVerdict
from app.agents.state import ResearchState
from app.agents.writing_runtime import WritingRoleServices
from app.agents.writing_support import _report_sections, _review_batches, _claim_lineage_findings
from app.prompts import render_prompt
from app.services.academic_writing import writing_guidance
from app.services.agent_run import estimate_cost, extract_tokens
from app.services.evidence_review import prepare_evidence_review, evaluate_evidence_reviews
from app.services.manuscript import manuscript_provenance, validate_manuscript, normalize_claim_markers
from app.services.provider_budget import ProviderBudgetExceeded
from app.services.research_quality import query_coverage, bounded_quality_batches, LEDGER_HEADINGS
from app.services.scientific_paper import validate_scientific_reporting

async def run_critic(state: ResearchState, services: WritingRoleServices) -> Dict[str, Any]:
    """Review every section using bounded, evidence-grounded provider calls."""
    _record_progress = services.record_progress
    record_agent_run = services.record_agent_run
    get_active_model_name = services.get_active_model_name
    get_fast_llm = services.get_fast_llm
    invoke_llm_with_budget = services.invoke_llm_with_budget
    BudgetedFallbackLLM = services.budgeted_llm_type
    await _record_progress(state, "CRITIC")
    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)
    model_name = get_active_model_name(is_smart=False)
    critic_contract = (state.get("plan") or {}).get("manuscript_contract") or {}
    critic_output_tokens = 2048 if critic_contract.get("evidence_review_policy") else 768
    from app.services.model_connection import current_connection
    if connection := current_connection():
        critic_output_tokens = min(connection.output_token_limit, 8192)
    base_llm = get_fast_llm()
    if isinstance(base_llm, BudgetedFallbackLLM):
        for _, client in base_llm.models:
            if hasattr(client, "max_output_tokens"):
                client.max_output_tokens = critic_output_tokens
            elif hasattr(client, "max_tokens"):
                client.max_tokens = critic_output_tokens
    llm = base_llm.with_structured_output(CriticVerdict)
    draft = normalize_claim_markers(state.get("draft_report_markdown", ""))
    review_records: list[dict[str, Any]] = []
    feedback: list[str] = []
    missing_areas: list[str] = []
    verdicts: list[str] = []
    token_totals = [0, 0]
    contract = (state.get("plan") or {}).get("manuscript_contract")
    manuscript_findings = validate_manuscript(draft, contract)
    manuscript_findings += validate_scientific_reporting(draft, contract, state.get("scientific_context") or {}, state.get("scientific_figures") or [])
    try:
        policy_version = ((contract or {}).get("evidence_review_policy") or {}).get("version", 1)
        sections = _report_sections(draft)
        if policy_version >= 2:
            sections = [(name, text) for name, text in sections if name.rsplit(" / ", 1)[-1] not in LEDGER_HEADINGS]
        if not sections:
            sections = [("Full report", "(The writer produced an empty report.)")]
        claims = state.get("claims", [])
        evidence_context = [
            {
                "claim_id": item.get("claim_id"),
                "claim": str(item.get("claim") or item.get("claim_text") or "")[:500],
                "evidence_id": item.get("evidence_id"),
                "evidence": str(item.get("evidence_quote") or item.get("evidence_text") or "")[:800],
                "source_id": item.get("source_id"),
                "chunk_id": item.get("chunk_id"),
                "source": str(item.get("source_title") or item.get("source_url") or "")[:300],
                "text_scope": item.get("text_scope"),
                "doi": item.get("doi"),
                "venue": item.get("venue"),
            }
            for item in claims[:50]
        ]
        protocol_context = state.get("protocol") or {}
        analysis_context = state.get("analysis_run") or {}
        batches = bounded_quality_batches(sections) if policy_version >= 2 else _review_batches(sections)
        support_audits = []
        require_support_review = bool((contract or {}).get("evidence_review_policy"))
        for section_names, section_text in batches:
            section_label = ", ".join(section_names)
            prepared = prepare_evidence_review(
                section_text, claims, draft=draft,
                central_headings=[s["heading"] for s in (contract or {}).get("sections", [])
                                  if s["id"] in {"discussion", "conclusion"}],
                policy_version=policy_version,
                execution_context=state.get("scientific_context") or {},
                excluded_headings=[s["heading"] for s in (contract or {}).get("sections", []) if s["id"] == "keywords"] + LEDGER_HEADINGS,
            ) if require_support_review else None
            selected_evidence = prepared["evidence"] if prepared else evidence_context
            support_instructions = ""
            if prepared:
                import json
                support_instructions = render_prompt(
                    'critic_evidence_support',
                    evidence_context_json=json.dumps(prepared['evidence'], ensure_ascii=False),
                    execution_facts_json=json.dumps(prepared['execution_facts'], ensure_ascii=False),
                    review_units_json=json.dumps(prepared['units'], ensure_ascii=False),
                    coverage_findings_json=json.dumps(prepared['coverage_findings']),
                )
            prompt = render_prompt('critic',
                research_type=state.get('research_type', 'REVIEW'),
                research_question=state.get('research_question'),
                required_sections=(state.get('plan') or {}).get('required_sections', []),
                manuscript_outline=[name for name, _ in sections],
                report_length=state.get('report_length', 'MEDIUM'),
                contract_version=contract.get('version') if contract else None,
                article_type=contract.get('article_type') if contract else None,
                contract_sections=(contract or {}).get('sections', []),
                writing_guidance=writing_guidance(contract, reviewer=True),
                editorial_findings=manuscript_findings,
                search_provenance=manuscript_provenance(state),
                evidence_need_coverage=state.get('evidence_need_coverage') or {},
                scientific_context=state.get('scientific_context'),
                figure_inventory=[{'number': f['number'], 'caption': f['caption'], 'kind': f['kind']} for f in state.get('scientific_figures', [])],
                has_user_data=bool(state.get('user_data_submission')),
                user_data_summary={key: (state.get('user_data_submission') or {}).get(key) for key in ('sample_size', 'method_notes', 'results_summary', 'data_provenance')},
                fieldwork_statistics=(state.get('scientific_context') or {}).get('fieldwork_csv_statistics'),
                has_analysis_run=bool(state.get('analysis_run')),
                protocol_context=protocol_context,
                analysis_routine=analysis_context.get('routine_name'),
                analysis_status=analysis_context.get('status'),
                analysis_metrics=analysis_context.get('metrics'),
                reproducibility_status=analysis_context.get('reproducibility_status'),
                selected_evidence=selected_evidence if not prepared else 'See EVIDENCE_REVIEW_CONTEXT_JSON below.',
                support_instructions=support_instructions,
                section_label=section_label,
                section_text=section_text,
            )
            verdict: CriticVerdict = await invoke_llm_with_budget(
                state, llm, [HumanMessage(content=prompt)], model_name=model_name,
                output_tokens=critic_output_tokens
            )
            in_tok, out_tok = extract_tokens(verdict, prompt_str=prompt, output_str=verdict.model_dump_json())
            token_totals[0] += in_tok
            token_totals[1] += out_tok
            normalized = verdict.verdict.upper()
            if normalized not in {"PASS", "REVISE", "NEED_MORE_DATA", "NEEDS_REVIEW"}:
                normalized = "NEEDS_REVIEW"
            bounded_feedback = verdict.feedback[:5]
            bounded_gaps = verdict.missing_areas[:5]
            verdicts.append(normalized)
            if prepared:
                support = evaluate_evidence_reviews(prepared, verdict.evidence_reviews)
                support["sections"] = section_names
                support["passages"] = prepared["units"]
                support_audits.append(support)
                feedback.extend(f"[{section_label}] {finding}" for finding in support["findings"])
                if support.get("substantive_findings"):
                    feedback.extend(support["substantive_findings"])
                    verdicts.append("REVISE")
                if not support["coverage_complete"]:
                    verdicts.append("NEEDS_REVIEW")
                for judgment in support["judgments"]:
                    if judgment["judgment"] != "SUPPORTED":
                        passage = next(u["passage"] for u in prepared["units"] if u["statement_id"] == judgment["statement_id"])
                        feedback.append(f"[{section_label}] Passage: {passage[:240]} — {judgment['judgment']}: {judgment['reason']}")
                        verdicts.append("NEEDS_REVIEW" if judgment["judgment"] == "UNVERIFIABLE" else "REVISE")
            feedback.extend(f"[{section_label}] {item}" for item in bounded_feedback)
            missing_areas.extend(bounded_gaps)
            review_records.append({
                "sections": section_names,
                "verdict": normalized,
                "feedback": bounded_feedback,
                "missing_areas": bounded_gaps,
                "evidence_support_complete": support["coverage_complete"] if prepared else None,
            })

        lineage_findings = _claim_lineage_findings(draft, claims)
        coverage = query_coverage(state)
        coverage_evaluable = any(e.get("query") for e in state.get("search_activity", []))
        need_coverage = state.get("evidence_need_coverage") or {}
        from app.services.evidence_selection import blocking_evidence_gaps
        blocking_need_ids = blocking_evidence_gaps(need_coverage)
        missing_need_queries = [n.get("search_query") or n["question"] for n in need_coverage.get("needs", [])
                                if n["need_id"] in blocking_need_ids]
        if (state.get("plan") or {}).get("evidence_needs") and missing_need_queries and not state.get("editorial_revision"):
            feedback.append("Planned evidence needs still have no matched source quote; narrow the manuscript or retrieve supporting material.")
            missing_areas = list(dict.fromkeys(missing_need_queries + missing_areas))
            verdicts.append("NEED_MORE_DATA" if len(state.get("collected_sources", [])) < state.get("max_sources", 10) else "NEEDS_REVIEW")
        if (contract or {}).get("research_quality_policy") and coverage_evaluable and coverage["missing_queries"]:
            missing_areas.extend(coverage["missing_queries"])
            feedback.append("No accepted source represents these planned discovery queries: " + "; ".join(coverage["missing_queries"]))
            verdicts.append("NEED_MORE_DATA" if len(state.get("collected_sources", [])) < state.get("max_sources", 10) else "NEEDS_REVIEW")
        if manuscript_findings:
            feedback.extend(item["message"] for item in manuscript_findings)
            nonrepairable_findings = {"SINGLE_SOURCE_SCOPE"}
            if any(item.get("code") in nonrepairable_findings for item in manuscript_findings):
                # More prose cannot create independent literature evidence.
                # Keep a requested research pass or a separate prose repair
                # available; final delivery still remains NEEDS_REVIEW unless
                # new evidence resolves this scope finding.
                if "NEED_MORE_DATA" not in verdicts and "REVISE" not in verdicts:
                    verdicts.append("NEEDS_REVIEW")
            if any(item.get("code") not in nonrepairable_findings for item in manuscript_findings):
                verdicts.append("REVISE")
        if state.get("draft_truncated"):
            feedback.append("The provider truncated the draft at its output limit. Rewrite concisely with all required sections and complete citation markers.")
            verdicts.append("REVISE")
        feedback.extend(lineage_findings)
        if lineage_findings:
            verdicts.append("REVISE" if all(item.startswith("Malformed or incomplete") for item in lineage_findings) else "NEEDS_REVIEW")
        previous = state.get("critic_review_metadata") or {}
        draft_hash = hashlib.sha256(draft.encode("utf-8")).hexdigest()
        no_delta_revision = state.get("current_micro_revision", 0) > 0 and previous.get("draft_sha256") == draft_hash
        if no_delta_revision:
            feedback.append("Writer revision produced no manuscript change; automatic revision stopped.")
            verdicts.append("NEEDS_REVIEW")

        if "NEEDS_REVIEW" in verdicts:
            final_verdict = "NEEDS_REVIEW"
        elif "NEED_MORE_DATA" in verdicts:
            final_verdict = "NEED_MORE_DATA"
        elif "REVISE" in verdicts:
            final_verdict = "REVISE"
        else:
            final_verdict = "PASS"
        scope_repair = False
        revision_policy = (contract or {}).get("revision_policy") or {}
        if (revision_policy.get("version", 1) >= 2 and final_verdict == "NEEDS_REVIEW"
                and "REVISE" in verdicts and blocking_need_ids
                and not lineage_findings and not no_delta_revision
                and not any(record["verdict"] == "NEEDS_REVIEW" for record in review_records)
                and state.get("current_micro_revision", 0) < state.get("max_micro_revisions", 2)):
            # Missing literature prevents scientific completion, but need not
            # prevent a bounded repair of identifiable overclaims/prose defects.
            # The next review and delivery independently recheck the same gaps.
            feedback.append("Repair the identified text using only supplied evidence. Narrow unsupported claims and disclose missing literature; do not invent support or results to fill a gap.")
            final_verdict = "REVISE"
            scope_repair = True
        if final_verdict == "REVISE" and state.get("current_micro_revision", 0) >= state.get("max_micro_revisions", 2):
            feedback.append("The automatic revision limit was reached; remaining findings need human review.")
            final_verdict = "NEEDS_REVIEW"
        review_metadata = {
            "status": "PASSED" if final_verdict == "PASS" else "NEEDS_REVIEW",
            "verdict": final_verdict,
            "sections_reviewed": [name for name, _ in sections],
            "section_reviews": review_records,
            "lineage_findings": lineage_findings,
            "manuscript_findings": manuscript_findings,
            "manuscript_contract_version": contract.get("version") if contract else None,
            "manuscript_contract": contract,
            "method_provenance": manuscript_provenance(state),
            "source_query_coverage": coverage,
            "evidence_need_coverage": need_coverage,
            "revision_limit": state.get("max_micro_revisions", 2),
            "draft_sha256": draft_hash,
            "automatic_revision_stopped": final_verdict == "NEEDS_REVIEW",
            "scope_repair_with_missing_evidence": scope_repair,
            "review_scope": "internal_quality_control_not_peer_review",
        }
        if require_support_review:
            review_metadata["evidence_support_review"] = {
                "version": policy_version, "draft_sha256": draft_hash,
                "coverage_complete": all(a["coverage_complete"] for a in support_audits),
                "all_supported": all(a["all_supported"] for a in support_audits),
                "expected_passages": sum(a["expected_passages"] for a in support_audits),
                "reviewed_passages": sum(a["reviewed_passages"] for a in support_audits),
                "batches": support_audits,
                "scope": "internal_llm_support_assessment_not_formal_verification",
            }
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        cost = estimate_cost(model_name, token_totals[0], token_totals[1])
        micro_count = state.get("current_micro_revision", 0) + 1 if final_verdict == "REVISE" else state.get("current_micro_revision", 0)

        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Critic",
            status="SUCCESS",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_tokens=token_totals[0],
            output_tokens=token_totals[1],
            estimated_cost=cost,
            input_summary={"reviewed_sections": len(sections), "review_calls": len(batches), "complete_draft_length": len(draft)},
            output_summary={"verdict": final_verdict, "feedback_count": len(feedback), "missing_areas_count": len(missing_areas)},
            tool_calls=[],
        )

        return {
            "current_agent": "critic",
            "critic_verdict": final_verdict,
            "critic_feedback": feedback[:50],
            "delta_queries": missing_areas[:25],
            "current_micro_revision": micro_count,
            "critic_review_metadata": review_metadata,
        }
    except ProviderBudgetExceeded as exc:
        # Respect the existing provider budget and preserve a reviewable draft.
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        completed_at = datetime.now(timezone.utc)
        metadata = {
            "status": "NEEDS_REVIEW",
            "verdict": "NEEDS_REVIEW",
            "sections_reviewed": [name for record in review_records for name in record.get("sections", [])],
            "section_reviews": review_records,
            "budget_limited": True,
            "automatic_revision_stopped": True,
            "review_scope": "internal_quality_control_not_peer_review",
        }
        await record_agent_run(
            task_id=state.get("task_id"), agent_name="Critic", status="SUCCESS",
            iteration=state.get("current_iteration", 0), attempt_number=state.get("attempt_number", 1),
            model=model_name, started_at=started_at, completed_at=completed_at,
            duration_ms=duration_ms, input_tokens=token_totals[0], output_tokens=token_totals[1],
            estimated_cost=estimate_cost(model_name, token_totals[0], token_totals[1]),
            input_summary={"reviewed_sections": len(review_records), "complete_draft_length": len(draft)},
            output_summary={"verdict": "NEEDS_REVIEW", "budget_limited": True}, tool_calls=[],
        )
        return {
            "current_agent": "critic", "critic_verdict": "NEEDS_REVIEW",
            "critic_feedback": [f"Whole-report review stopped at the provider budget limit: {exc}"],
            "critic_review_metadata": metadata,
            "current_micro_revision": state.get("current_micro_revision", 0),
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await record_agent_run(
            task_id=state.get("task_id"),
            agent_name="Critic",
            status="FAILED",
            iteration=state.get("current_iteration", 0),
            attempt_number=state.get("attempt_number", 1),
            model=model_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise
