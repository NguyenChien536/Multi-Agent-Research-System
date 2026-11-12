# backend/app/services/execution_evidence.py
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

FACT_ID: str = "analysis.manifest.parameters.seed"
FACT_SCOPE: str = "executed seeded partition only; not scientific generalization"
MAX_PARAGRAPH_LEN: int = 700

SUPPORTED_ROUTINES: frozenset[str] = frozenset(
    {
        "tabular_regression_v1",
    }
)

# Reject paragraphs asserting overarching scientific, normative, optimality, or privacy guarantees.
# All expressions evaluated against fold_accents(text).
DISALLOWED_TERMS: tuple[str, ...] = (
    # English terms
    r"\bstab(?:ility|le)\b",
    r"\bstrategy[- ]proof(?:ness)?\b",
    r"\bpareto\b",
    r"\boptimal(?:ity)?\b",
    r"\bfair(?:ness)?\b",
    r"\bcausality\b",
    r"\bcausal\b",
    r"\bstatistical(?:ly)?\s+significan(?:ce|t)\b",
    r"\baccuracy\b",
    r"\bsuperior(?:ity)?\b",
    r"\boutperform\w*\b",
    r"\bsignificantly\s+better\b",
    r"\ball\s+datasets\b",
    r"\balways\b",
    r"\bevery\s+dataset\b",
    r"\buniversal(?:ly)?\b",
    r"\banonymity\b",
    r"\bprivacy\b",
    # Folded Vietnamese terms
    r"\bon\s+dinh\b",
    r"\bcong\s+bang\b",
    r"\bnhan\s+qua\b",
    r"\bbao\s+mat\b",
    r"\brieng\s+tu\b",
    r"\btot\s+nhat\b",
    r"\by\s+nghia\s+thong\s+ke\b",
    r"\bchinh\s+xac\b",
    r"\bvuot\s+troi\b",
    r"\bluon\s+luon\b",
    r"\bmoi\s+tap\s+du\s+lieu\b",
)

DISALLOWED_RE: re.Pattern[str] = re.compile(
    "|".join(f"(?:{term})" for term in DISALLOWED_TERMS),
    re.IGNORECASE,
)

# Mandatory procedural anchors: deterministic / repeatable allocation, partition, or split.
DETERMINISTIC_STEMS: tuple[str, ...] = (
    r"deterministic",
    r"fixed",
    r"repeatable",
    r"reproducible",
    r"xac dinh",
    r"co dinh",
    r"lap lai",
)

PARTITION_STEMS: tuple[str, ...] = (
    r"partition(?:ing|ed|s)?",
    r"split(?:ting|s)?",
    r"allocation",
    r"allocate(?:d)?",
    r"phan chia",
    r"phan bo",
    r"chia tach",
)

DETERMINISTIC_RE: re.Pattern[str] = re.compile(
    "|".join(f"(?:{stem})" for stem in DETERMINISTIC_STEMS),
    re.IGNORECASE,
)

PARTITION_RE: re.Pattern[str] = re.compile(
    "|".join(f"(?:{stem})" for stem in PARTITION_STEMS),
    re.IGNORECASE,
)

SEED_MENTION_RE: re.Pattern[str] = re.compile(
    r"\bseed\s*(?:=|:|is|of)?\s*(-?\d+)(?!\d|\.\d)\b",
    re.IGNORECASE,
)


def fold_accents(text: str) -> str:
    """Normalize text into lowercase ASCII by stripping Unicode accents/diacritics."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    # Vietnamese 'đ' / 'Đ' does not decompose into d + combining mark under NFKD
    stripped = stripped.replace("đ", "d").replace("Đ", "d")
    return stripped.lower()


def execution_procedure_fact(
    paragraph: str,
    context: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Pure function validating procedural claims regarding a seeded execution partition.

    Extracts a bounded fact only when:
      1. Context describes a completed, reproducibility-passed, supported routine with an int seed.
      2. Paragraph is within length limit and does not make forbidden scientific/privacy claims.
      3. Paragraph explicitly asserts a deterministic/fixed/repeatable partition/split.
      4. Paragraph explicitly binds to the actual execution seed without mismatching mentions.
    """
    if not isinstance(paragraph, str) or not paragraph.strip():
        return None
    if len(paragraph) > MAX_PARAGRAPH_LEN:
        return None
    if not isinstance(context, Mapping):
        return None

    analysis = context.get("analysis")
    if not isinstance(analysis, Mapping):
        return None

    analysis_run_id = analysis.get("analysis_run_id")
    if not isinstance(analysis_run_id, str) or not analysis_run_id.strip():
        return None

    if analysis.get("status") != "COMPLETED":
        return None
    if analysis.get("reproducibility_status") != "PASSED":
        return None

    routine_name = analysis.get("routine_name")
    if not isinstance(routine_name, str) or routine_name not in SUPPORTED_ROUTINES:
        return None

    manifest = analysis.get("manifest")
    if not isinstance(manifest, Mapping):
        return None

    parameters = manifest.get("parameters")
    if not isinstance(parameters, Mapping):
        return None

    actual_seed = parameters.get("seed")
    # Require strictly an integer, explicitly rejecting boolean instances
    if isinstance(actual_seed, bool) or not isinstance(actual_seed, int):
        return None

    folded_text = fold_accents(paragraph)

    # Reject any scientific, optimality, fairness, or privacy guarantees
    if DISALLOWED_RE.search(folded_text):
        return None

    # Must describe deterministic/repeatable procedure
    if not DETERMINISTIC_RE.search(folded_text):
        return None

    # Must describe partition/split/allocation
    if not PARTITION_RE.search(folded_text):
        return None

    # Check explicit seed mentions in paragraph
    seed_matches = SEED_MENTION_RE.findall(folded_text)
    if not seed_matches:
        return None

    # Reject if any mentioned seed deviates from actual_seed
    try:
        seeds_found = [int(m) for m in seed_matches]
    except ValueError:
        return None

    if any(s != actual_seed for s in seeds_found):
        return None

    return {
        "fact_id": FACT_ID,
        "value": actual_seed,
        "analysis_run_id": str(analysis_run_id),
        "scope": FACT_SCOPE,
    }
