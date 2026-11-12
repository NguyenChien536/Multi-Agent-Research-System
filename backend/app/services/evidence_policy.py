"""Minimum evidence gate. Provenance presence is not semantic truth verification."""

class InsufficientEvidence(RuntimeError):
    pass

def has_writing_evidence(state: dict) -> bool:
    for claim in state.get('claims') or []:
        if all(claim.get(key) for key in ('claim_id','evidence_id','source_id','chunk_id')) and (
            claim.get('claim') or claim.get('claim_text') or '').strip() and (
            claim.get('evidence_quote') or claim.get('evidence_text') or '').strip():
            return True
    analysis = state.get('analysis_run') or {}
    if analysis.get('status') == 'COMPLETED' and analysis.get('analysis_run_id') and analysis.get('metrics'):
        return True
    submission = state.get('user_data_submission') or {}
    artifact = submission.get('artifact_evidence') or {}
    return bool(artifact.get('sha256_hash') and submission.get('file_artifact_id')
                and submission.get('results_summary') and submission.get('data_provenance'))
