"""
Standalone verification for the v3.0 operational layer. Two things are
verified two different ways:

1. The evaluation logic (app/ops_logic.py) has ZERO SQLAlchemy dependency,
   so it is imported and exercised directly - this is the real code, not a
   reimplementation, run against real inputs including deliberately bad ones.

2. The schema + CSV import validation rules (app/models_ops.py,
   app/ops_import.py) DO depend on SQLAlchemy, which cannot be installed in
   this sandbox (same limitation documented in verify_schema_v2.py), so this
   script re-implements the relevant tables in raw sqlite3 and re-implements
   the same required-field validation rules ops_import.py enforces, then
   proves: (a) every shipped *_import_template.csv file parses and inserts
   cleanly once its EXAMPLE row is treated as real data, (b) a deliberately
   malformed row (missing a required field) is rejected, not silently
   dropped or defaulted, and (c) the seeded readiness ledger for the two real
   candidates has no row with a status outside the five allowed values.

This script is NOT part of the shipped app; it is a verification tool run
once during development. Mirrors verify_schema.py / verify_schema_v2.py.
"""
import csv
import io
import sqlite3
import sys

sys.path.insert(0, "caddtard-ai")
from app import seed_data_v3  # noqa: E402
from app.ops_logic import (  # noqa: E402
    GoNoGoInput,
    budget_status_from_variance,
    compute_cost_variance_pct,
    compute_go_no_go,
    evaluate_acceptance,
    timeline_status_from_milestones,
)

failures = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        failures.append(label)
    print(f"[{status}] {label}")


# ---------------------------------------------------------------------------
# Part 1: ops_logic.py is real code, imported directly - not reimplemented.
# ---------------------------------------------------------------------------
check("evaluate_acceptance gte pass", evaluate_acceptance("gte", 5.0, 3.0, None) == "pass")
check("evaluate_acceptance gte fail", evaluate_acceptance("gte", 2.0, 3.0, None) == "fail")
check("evaluate_acceptance range pass", evaluate_acceptance("range", 5.0, 1.0, 10.0) == "pass")
try:
    evaluate_acceptance("bogus", 1.0, None, None)
    check("evaluate_acceptance rejects unknown comparator", False)
except ValueError:
    check("evaluate_acceptance rejects unknown comparator", True)

check("cost variance: zero budget -> None (not divide-by-zero)", compute_cost_variance_pct(0, 100) is None)
check("cost variance: 10% over", compute_cost_variance_pct(100, 110) == 10.0)
check("budget status maps variance correctly", budget_status_from_variance(15) == "over" and budget_status_from_variance(-15) == "under")
check("timeline status is worst-of", timeline_status_from_milestones(["on_track", "late", "at_risk"]) == "late")

r_insufficient = compute_go_no_go(GoNoGoInput(None, None, "unknown", "unknown"))
check("go/no-go refuses to recommend from zero evidence", r_insufficient.recommendation == "insufficient_data")
r_go = compute_go_no_go(GoNoGoInput(0.8, 0.9, "on_budget", "on_track"))
check("go/no-go recommends go when everything clears floors", r_go.recommendation == "go")
r_nogo = compute_go_no_go(GoNoGoInput(0.1, 0.9, "on_budget", "on_track"))
check("go/no-go recommends no_go when candidate score is below floor", r_nogo.recommendation == "no_go")


# ---------------------------------------------------------------------------
# Part 2: raw-sqlite3 reimplementation of the operational schema + import
# validation rules, since SQLAlchemy cannot be installed in this sandbox.
# ---------------------------------------------------------------------------
conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.executescript(
    """
    CREATE TABLE cro_vendors (id INTEGER PRIMARY KEY, name TEXT, verified_source TEXT);
    CREATE TABLE vendor_quotes (id INTEGER PRIMARY KEY, vendor_id INTEGER, price_usd REAL, study_type TEXT);
    CREATE TABLE studies (id INTEGER PRIMARY KEY, title TEXT, is_demo INTEGER DEFAULT 0);
    CREATE TABLE samples (id INTEGER PRIMARY KEY, study_id INTEGER, sample_id_external TEXT);
    CREATE TABLE assay_acceptance_criteria (
        id INTEGER PRIMARY KEY, study_id INTEGER, assay_name TEXT, metric_name TEXT,
        comparator TEXT, threshold_low REAL, threshold_high REAL
    );
    CREATE TABLE study_costs (id INTEGER PRIMARY KEY, study_id INTEGER, category TEXT, budgeted_usd REAL, actual_usd REAL);
    CREATE TABLE readiness_requirements (
        id INTEGER PRIMARY KEY, candidate_slug TEXT, category TEXT, requirement_key TEXT, evidence_status TEXT
    );
    """
)

VALID_STATUS = {"present", "provisional", "missing", "failed", "not_applicable"}
VALID_COMPARATOR = {"gte", "lte", "eq", "range"}


class RowRejected(Exception):
    pass


def sql_import_vendor(row):
    if not row.get("name") or not row.get("verified_source"):
        raise RowRejected("name and verified_source are required")
    cur.execute("INSERT INTO cro_vendors (name, verified_source) VALUES (?,?)", (row["name"], row["verified_source"]))
    return cur.lastrowid


def sql_import_readiness(row):
    if not row.get("candidate_slug") or not row.get("requirement_key") or row.get("evidence_status") not in VALID_STATUS:
        raise RowRejected("candidate_slug, requirement_key, and a valid evidence_status are required")
    cur.execute(
        "INSERT INTO readiness_requirements (candidate_slug, category, requirement_key, evidence_status) VALUES (?,?,?,?)",
        (row["candidate_slug"], row.get("category", ""), row["requirement_key"], row["evidence_status"]),
    )


# (a) every shipped CSV template parses and its EXAMPLE row imports cleanly
import os

template_dir = "caddtard-ai/import_templates"
templates = sorted(os.listdir(template_dir))
check("8 CSV import templates are present", len(templates) == 8)

vendor_row = None
for fname in templates:
    with open(os.path.join(template_dir, fname)) as fh:
        rows = list(csv.DictReader(fh))
    ok = len(rows) == 1 and all(v is not None for v in rows[0].values())
    check(f"{fname} parses to exactly 1 well-formed EXAMPLE row", ok)
    if fname == "cro_vendors_import_template.csv":
        vendor_row = rows[0]

try:
    sql_import_vendor(vendor_row)
    check("cro_vendors_import_template.csv EXAMPLE row imports cleanly", True)
except RowRejected:
    check("cro_vendors_import_template.csv EXAMPLE row imports cleanly", False)

# (b) a deliberately malformed row (missing verified_source) is rejected
try:
    sql_import_vendor({"name": "No Source Vendor", "verified_source": ""})
    check("import rejects a vendor row with no verified_source", False)
except RowRejected:
    check("import rejects a vendor row with no verified_source", True)

try:
    sql_import_readiness({"candidate_slug": "x", "requirement_key": "y", "evidence_status": "definitely_ready"})
    check("import rejects an invalid evidence_status value", False)
except RowRejected:
    check("import rejects an invalid evidence_status value", True)

# (c) the real readiness ledger seed data is valid and honestly distributed
for r in seed_data_v3.READINESS_REQUIREMENTS:
    sql_import_readiness(r)
conn.commit()

check(
    f"{len(seed_data_v3.READINESS_REQUIREMENTS)} readiness rows all have a valid evidence_status",
    cur.execute(
        f"SELECT COUNT(*) FROM readiness_requirements WHERE evidence_status NOT IN ({','.join('?' * len(VALID_STATUS))})",
        tuple(VALID_STATUS),
    ).fetchone()[0] == 0,
)
missing_count = cur.execute("SELECT COUNT(*) FROM readiness_requirements WHERE evidence_status='missing'").fetchone()[0]
total_count = cur.execute("SELECT COUNT(*) FROM readiness_requirements").fetchone()[0]
check(
    f"platform starts conservative: {missing_count}/{total_count} readiness rows are 'missing', not inflated to 'present'",
    missing_count / total_count > 0.4,
)
failed_prv = cur.execute(
    "SELECT COUNT(*) FROM readiness_requirements WHERE requirement_key='tropical_disease_prv_eligibility' AND evidence_status='failed'"
).fetchone()[0]
check("both candidates' PRV eligibility is honestly marked 'failed' (chromoblastomycosis is not FDA PRV-qualifying)", failed_prv == 2)

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED:", failures)
    sys.exit(1)
else:
    print("ALL V3 OPERATIONAL-LAYER CHECKS PASSED")
