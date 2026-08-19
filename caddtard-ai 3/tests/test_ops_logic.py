"""
Real pytest coverage for app/ops_logic.py - the pure evaluation functions
behind assay acceptance grading, cost variance, and go/no-go governance.
This module has zero SQLAlchemy dependency by design, so these tests need no
DB fixture at all (contrast with test_api.py / test_api_v2.py, which do).
"""
import pytest

from app.ops_logic import (
    GoNoGoInput,
    budget_status_from_variance,
    compute_cost_variance_pct,
    compute_go_no_go,
    evaluate_acceptance,
    timeline_status_from_milestones,
)


@pytest.mark.parametrize(
    "comparator,measured,low,high,expected",
    [
        ("gte", 5.0, 3.0, None, "pass"),
        ("gte", 2.0, 3.0, None, "fail"),
        ("lte", 2.0, None, 3.0, "pass"),
        ("lte", 4.0, None, 3.0, "fail"),
        ("eq", 3.0, 3.0, None, "pass"),
        ("eq", 3.1, 3.0, None, "fail"),
        ("range", 5.0, 1.0, 10.0, "pass"),
        ("range", 15.0, 1.0, 10.0, "fail"),
    ],
)
def test_evaluate_acceptance(comparator, measured, low, high, expected):
    assert evaluate_acceptance(comparator, measured, low, high) == expected


def test_evaluate_acceptance_rejects_unknown_comparator():
    with pytest.raises(ValueError):
        evaluate_acceptance("bogus", 1.0, None, None)


def test_evaluate_acceptance_requires_thresholds():
    with pytest.raises(ValueError):
        evaluate_acceptance("gte", 1.0, None, None)


def test_cost_variance_zero_budget_is_none_not_divide_by_zero():
    assert compute_cost_variance_pct(0, 100) is None


def test_cost_variance_sign():
    assert compute_cost_variance_pct(100, 110) == 10.0
    assert compute_cost_variance_pct(100, 90) == -10.0


@pytest.mark.parametrize(
    "variance,expected",
    [(None, "unknown"), (15, "over"), (-15, "under"), (5, "on_budget")],
)
def test_budget_status_from_variance(variance, expected):
    assert budget_status_from_variance(variance) == expected


def test_timeline_status_worst_of():
    assert timeline_status_from_milestones([]) == "unknown"
    assert timeline_status_from_milestones(["on_track", "late"]) == "late"
    assert timeline_status_from_milestones(["on_track", "at_risk"]) == "at_risk"
    assert timeline_status_from_milestones(["on_track", "complete"]) == "on_track"


def test_go_no_go_refuses_to_recommend_from_zero_evidence():
    r = compute_go_no_go(GoNoGoInput(None, None, "unknown", "unknown"))
    assert r.recommendation == "insufficient_data"


def test_go_no_go_recommends_go_when_everything_clears():
    r = compute_go_no_go(GoNoGoInput(0.8, 0.9, "on_budget", "on_track"))
    assert r.recommendation == "go"


def test_go_no_go_recommends_no_go_below_score_floor():
    r = compute_go_no_go(GoNoGoInput(0.2, 0.9, "on_budget", "on_track"))
    assert r.recommendation == "no_go"


def test_go_no_go_recommends_no_go_below_assay_floor():
    r = compute_go_no_go(GoNoGoInput(0.8, 0.3, "on_budget", "on_track"))
    assert r.recommendation == "no_go"


def test_go_no_go_holds_on_marginal_evidence():
    r = compute_go_no_go(GoNoGoInput(0.8, 0.6, "on_budget", "on_track"))
    assert r.recommendation == "hold"


def test_go_no_go_no_go_when_over_budget():
    r = compute_go_no_go(GoNoGoInput(0.8, 0.9, "over", "on_track"))
    assert r.recommendation == "no_go"


def test_go_no_go_no_go_when_timeline_late():
    r = compute_go_no_go(GoNoGoInput(0.8, 0.9, "on_budget", "late"))
    assert r.recommendation == "no_go"
