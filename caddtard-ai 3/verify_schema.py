"""
Standalone verification: re-implements the SQL schema in raw sqlite3 (stdlib
only, no SQLAlchemy) and replays the seed data + the same assertions as
tests/test_api.py, to prove the relational design and seed dataset are
internally consistent even though SQLAlchemy/FastAPI could not be installed
in this environment. This script is NOT part of the shipped app; it is a
verification tool run once during development.
"""
import sqlite3
import sys

sys.path.insert(0, "caddtard-ai")
from app import seed_data  # noqa: E402

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.executescript(
    """
    CREATE TABLE genes (
        id INTEGER PRIMARY KEY,
        symbol TEXT UNIQUE,
        uniprot_accession TEXT,
        in_top3 INTEGER,
        xlsx_uniprot_claim TEXT
    );
    CREATE TABLE variants (
        id INTEGER PRIMARY KEY,
        gene_id INTEGER REFERENCES genes(id),
        mutation TEXT
    );
    CREATE TABLE scoring_candidates (
        id INTEGER PRIMARY KEY,
        program TEXT,
        composite REAL,
        selected INTEGER
    );
    CREATE TABLE candidates (
        id INTEGER PRIMARY KEY,
        slug TEXT UNIQUE,
        name TEXT
    );
    CREATE TABLE timeline_items (
        id INTEGER PRIMARY KEY,
        candidate_id INTEGER REFERENCES candidates(id),
        month_label TEXT,
        sort_order INTEGER
    );
    CREATE TABLE cost_summaries (
        id INTEGER PRIMARY KEY,
        candidate_slug TEXT UNIQUE,
        allin_low_usd_k REAL,
        allin_high_usd_k REAL
    );
    CREATE TABLE checklist_items (
        id INTEGER PRIMARY KEY,
        candidate_slug TEXT,
        label TEXT,
        checked INTEGER DEFAULT 0
    );
    """
)

gene_ids = {}
for g in seed_data.GENES:
    cur.execute(
        "INSERT INTO genes (symbol, uniprot_accession, in_top3, xlsx_uniprot_claim) VALUES (?,?,?,?)",
        (g["symbol"], g["uniprot_accession"], int(g["in_top3"]), g["xlsx_uniprot_claim"]),
    )
    gene_ids[g["symbol"]] = cur.lastrowid

for v in seed_data.VARIANTS:
    gid = gene_ids.get(v["gene_symbol"])
    assert gid is not None, f"variant references unknown gene {v['gene_symbol']}"
    cur.execute("INSERT INTO variants (gene_id, mutation) VALUES (?,?)", (gid, v["mutation"]))

for s in seed_data.SCORING:
    cur.execute(
        "INSERT INTO scoring_candidates (program, composite, selected) VALUES (?,?,?)",
        (s["program"], s["composite"], int(s["selected"])),
    )

cand_ids = {}
for c in seed_data.CANDIDATES:
    cur.execute("INSERT INTO candidates (slug, name) VALUES (?,?)", (c["slug"], c["name"]))
    cand_ids[c["slug"]] = cur.lastrowid

for slug, items in seed_data.TIMELINE.items():
    cid = cand_ids[slug]
    for item in items:
        cur.execute(
            "INSERT INTO timeline_items (candidate_id, month_label, sort_order) VALUES (?,?,?)",
            (cid, item["month_label"], item["sort_order"]),
        )

for slug, summary in seed_data.COST_SUMMARY.items():
    cur.execute(
        "INSERT INTO cost_summaries (candidate_slug, allin_low_usd_k, allin_high_usd_k) VALUES (?,?,?)",
        (slug, summary["allin_low_usd_k"], summary["allin_high_usd_k"]),
    )

for slug in list(cand_ids.keys()) + ["global"]:
    for item in seed_data.CHECKLIST_DEFAULTS:
        cur.execute(
            "INSERT INTO checklist_items (candidate_slug, label, checked) VALUES (?,?,0)",
            (slug, item["label"]),
        )

conn.commit()

failures = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        failures.append(label)
    print(f"[{status}] {label}")


# Mirrors test_api.py assertions
check("13 genes total", cur.execute("SELECT COUNT(*) FROM genes").fetchone()[0] == 13)

top3_symbols = {r[0] for r in cur.execute("SELECT symbol FROM genes WHERE in_top3=1")}
check("top3 genes == {ATP6V0A4, ATP6V1B1, ATP6V0C, TCIRG1}",
      top3_symbols == {"ATP6V0A4", "ATP6V1B1", "ATP6V0C", "TCIRG1"})

row = cur.execute("SELECT uniprot_accession, xlsx_uniprot_claim FROM genes WHERE symbol='ATP6V0A4'").fetchone()
check("ATP6V0A4 uniprot=Q9HBG4 / xlsx claim=Q9H1X4", tuple(row) == ("Q9HBG4", "Q9H1X4"))

n_variants_atp6v0a4 = cur.execute(
    "SELECT COUNT(*) FROM variants v JOIN genes g ON v.gene_id=g.id WHERE g.symbol='ATP6V0A4'"
).fetchone()[0]
check("ATP6V0A4 has >0 variants", n_variants_atp6v0a4 > 0)

n_variants_tcirg1 = cur.execute(
    "SELECT COUNT(*) FROM variants v JOIN genes g ON v.gene_id=g.id WHERE g.symbol='TCIRG1'"
).fetchone()[0]
check("TCIRG1 has 0 variants (not in original xlsx)", n_variants_tcirg1 == 0)

scores = [r[0] for r in cur.execute("SELECT composite FROM scoring_candidates ORDER BY composite DESC")]
check("10 scoring rows, sorted desc matches Python sort", scores == sorted(scores, reverse=True) and len(scores) == 10)

cand_slugs = {r[0] for r in cur.execute("SELECT slug FROM candidates")}
check("candidates == {drta, atp6v0c, tcirg1}", cand_slugs == {"drta", "atp6v0c", "tcirg1"})

tl_count = cur.execute(
    "SELECT COUNT(*) FROM timeline_items t JOIN candidates c ON t.candidate_id=c.id WHERE c.slug='tcirg1'"
).fetchone()[0]
check("tcirg1 has >0 timeline rows", tl_count > 0)

cost_row = cur.execute("SELECT allin_low_usd_k FROM cost_summaries WHERE candidate_slug='tcirg1'").fetchone()
check("tcirg1 all-in low cost == 4000", cost_row[0] == 4000)

checklist_count = cur.execute("SELECT COUNT(*) FROM checklist_items WHERE candidate_slug='drta'").fetchone()[0]
check("drta checklist has 12 default items", checklist_count == 12)

cur.execute("UPDATE checklist_items SET checked=1 WHERE candidate_slug='drta' AND id = (SELECT MIN(id) FROM checklist_items WHERE candidate_slug='drta')")
conn.commit()
checked_count = cur.execute("SELECT COUNT(*) FROM checklist_items WHERE candidate_slug='drta' AND checked=1").fetchone()[0]
check("checklist toggle persists (1 item checked)", checked_count == 1)

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED:", failures)
    sys.exit(1)
else:
    print("ALL SCHEMA/SEED CHECKS PASSED")
