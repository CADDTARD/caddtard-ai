"""
Pure evaluation logic for the v3.0 operational layer: assay acceptance
grading, cost variance, and the go/no-go recommendation. Deliberately kept
free of any SQLAlchemy/FastAPI import so it can be unit-tested directly
(see tests/test_ops_logic.py and verify_ops_schema.py) and so the same
function the API calls is the exact function a plain-Python script can
call to reproduce a result by hand - no hidden state, nothing computed
inside an ORM event hook.
"""
from __future__ import annotations

from dataclasses import dataclass


def evaluate_acceptance(
    comparator: str,
    measured_value: float,
    threshold_low: float | None,
    threshold_high: float | None,
) -> str:
    """Grades one measured value against one prospective criterion.
    comparator: 'gte' | 'lte' | 'eq' | 'range'
    Returns 'pass' or 'fail'. Never returns anything else - an unrecognized
    comparator is a configuration bug and raises, rather than silently
    passing a result."""
    if comparator == "gte":
        if threshold_low is None:
            raise ValueError("gte comparator requires threshold_low")
        return "pass" if measured_value >= threshold_low else "fail"
    if comparator == "lte":
        if threshold_high is None:
            raise ValueError("lte comparator requires threshold_high")
        return "pass" if measured_value <= threshold_high else "fail"
    if comparator == "eq":
        if threshold_low is None:
            raise ValueError("eq comparator requires threshold_low")
        return "pass" if measured_value == threshold_low else "fail"
    if comparator == "range":
        if threshold_low is None or threshold_high is None:
            raise ValueError("range comparator requires threshold_low and threshold_high")
        return "pass" if threshold_low <= measured_value <= threshold_high else "fail"
    raise ValueError(f"Unrecognized comparator: {comparator!r}")


def compute_cost_variance_pct(budgeted_usd: float, actual_usd: float) -> float | None:
    """Positive = over budget, negative = under budget. None only when there
    is genuinely no budget on file (0), so a variance can't be computed -
    reported as None rather than a misleading 0% or a divide-by-zero."""
    if not budgeted_usd:
        return None
    return round(((actual_usd - budgeted_usd) / budgeted_usd) * 100, 2)


def budget_status_from_variance(variance_pct: float | None, tolerance_pct: float = 10.0) -> str:
    if variance_pct is None:
        return "unknown"
    if variance_pct > tolerance_pct:
        return "over"
    if variance_pct < -tolerance_pct:
        return "under"
    return "on_budget"


def timeline_status_from_milestones(milestone_statuses: list[str]) -> str:
    """milestone_statuses: list of 'on_track'|'at_risk'|'late'|'complete' pulled
    from StudyMilestone rows for one study. Worst-status-wins."""
    if not milestone_statuses:
        return "unknown"
    if "late" in milestone_statuses:
        return "late"
    if "at_risk" in milestone_statuses:
        return "at_risk"
    return "on_track"


@dataclass
class GoNoGoInput:
    measured_candidate_score: float | None  # 0-1, from the existing scoring/hypothesis-confidence layer; None if not yet measured
    assay_pass_rate: float | None  # 0-1, fraction of AssayAcceptanceEvaluation rows that passed; None if no evaluations exist yet
    budget_status: str  # 'on_budget'|'over'|'under'|'unknown'
    timeline_status: str  # 'on_track'|'at_risk'|'late'|'unknown'


@dataclass
class GoNoGoResult:
    recommendation: str  # 'go'|'no_go'|'hold'|'insufficient_data'
    rationale: str


def compute_go_no_go(inp: GoNoGoInput) -> GoNoGoResult:
    """Deliberately conservative: with no measured evidence at all, the system
    refuses to recommend 'go' or 'no_go' and returns 'insufficient_data'
    instead - the same "don't imply confidence you don't have" principle
    applied to the readiness ledger. A human can still make the call; the
    system just won't manufacture one for them."""
    reasons: list[str] = []

    if inp.measured_candidate_score is None and inp.assay_pass_rate is None:
        return GoNoGoResult(
            recommendation="insufficient_data",
            rationale="No measured candidate score and no assay acceptance evaluations are on file for this study yet. "
            "The system will not propose go/no-go from zero measured evidence.",
        )

    if inp.assay_pass_rate is not None and inp.assay_pass_rate < 0.5:
        reasons.append(f"assay acceptance pass rate is {inp.assay_pass_rate:.0%}, below the 50% floor")
    if inp.measured_candidate_score is not None and inp.measured_candidate_score < 0.4:
        reasons.append(f"measured candidate score is {inp.measured_candidate_score:.2f}, below the 0.40 floor")
    if inp.timeline_status == "late":
        reasons.append("one or more study milestones are late")
    if inp.budget_status == "over":
        reasons.append("study cost is over budget beyond tolerance")

    if reasons:
        return GoNoGoResult(recommendation="no_go", rationale="; ".join(reasons))

    caution: list[str] = []
    if inp.assay_pass_rate is not None and inp.assay_pass_rate < 0.8:
        caution.append(f"assay acceptance pass rate is only {inp.assay_pass_rate:.0%}")
    if inp.timeline_status == "at_risk":
        caution.append("a study milestone is at risk")
    if inp.budget_status == "unknown":
        caution.append("no cost data is on file to confirm budget status")

    if caution:
        return GoNoGoResult(recommendation="hold", rationale="; ".join(caution))

    return GoNoGoResult(
        recommendation="go",
        rationale="Measured candidate score and assay acceptance are both above floor, timeline is on track, and budget is within tolerance.",
    )
