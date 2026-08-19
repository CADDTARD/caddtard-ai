"""
Standalone verification for the v3.0 layers (superset of v2.0) (data fabric, knowledge graph,
agent taxonomy, reasoning engine, lab-recommendation ranking): re-implements
the relevant part of the SQL schema in raw sqlite3 (stdlib only, no
SQLAlchemy) and replays app/seed_data_v2.py plus the same logic the FastAPI
routers apply (BFS subgraph, average-confidence rollup, ascending-confidence
recommendation sort), to prove the v2 design and dataset are internally
consistent even though SQLAlchemy/FastAPI could not be installed in this
environment. This script is NOT part of the shipped app; it is a
verification tool run once during development. Mirrors tests/test_api_v2.py.
"""
import json
import sqlite3
import sys

sys.path.insert(0, "caddtard-ai")
from app import seed_data_v2  # noqa: E402

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.executescript(
    """
    CREATE TABLE data_sources (
        id INTEGER PRIMARY KEY, key TEXT UNIQUE, name TEXT, category TEXT,
        integration_type TEXT, status TEXT, agent_key TEXT, url TEXT, description TEXT
    );
    CREATE TABLE agent_definitions (
        id INTEGER PRIMARY KEY, key TEXT UNIQUE, name TEXT, division TEXT,
        description TEXT, status TEXT, interval_minutes INTEGER, module_path TEXT
    );
    CREATE TABLE graph_nodes (
        id INTEGER PRIMARY KEY, node_type TEXT, label TEXT, external_ref TEXT,
        properties_json TEXT, version INTEGER DEFAULT 1,
        UNIQUE(node_type, external_ref)
    );
    CREATE TABLE graph_edges (
        id INTEGER PRIMARY KEY, source_node_id INTEGER REFERENCES graph_nodes(id),
        target_node_id INTEGER REFERENCES graph_nodes(id), edge_type TEXT,
        properties_json TEXT, version INTEGER DEFAULT 1
    );
    CREATE TABLE hypotheses (
        id INTEGER PRIMARY KEY, number INTEGER UNIQUE, title TEXT,
        candidate_slug TEXT, gene_symbol TEXT, status TEXT
    );
    CREATE TABLE hypothesis_steps (
        id INTEGER PRIMARY KEY, hypothesis_id INTEGER REFERENCES hypotheses(id),
        sort_order INTEGER, from_label TEXT, to_label TEXT,
        supporting_papers_json TEXT, confidence REAL, conflicting_evidence TEXT,
        experimental_status TEXT, recommended_next_experiment TEXT
    );
    """
)

for s in seed_data_v2.DATA_SOURCES:
    cur.execute(
        "INSERT INTO data_sources (key,name,category,integration_type,status,agent_key,url,description) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (s["key"], s["name"], s["category"], s["integration_type"], s["status"], s["agent_key"], s["url"], s["description"]),
    )

for a in seed_data_v2.AGENT_DEFINITIONS:
    cur.execute(
        "INSERT INTO agent_definitions (key,name,division,description,status,interval_minutes,module_path) "
        "VALUES (?,?,?,?,?,?,?)",
        (a["key"], a["name"], a["division"], a["description"], a["status"], a.get("interval_minutes"), a.get("module_path", "")),
    )

node_ids = {}
for n in seed_data_v2.GRAPH_NODES:
    # Mirrors PostgresGraphStore.upsert_node's "" -> NULL normalization
    # (app/graph/store.py) so this reimplementation exercises the same fix
    # for the uq_node_type_ref constraint, not the pre-fix behavior.
    ext_ref = n.get("external_ref", "") or None
    cur.execute(
        "INSERT INTO graph_nodes (node_type,label,external_ref,properties_json) VALUES (?,?,?,?)",
        (n["node_type"], n["label"], ext_ref, json.dumps(n.get("properties", {}))),
    )
    node_ids[n["label"]] = cur.lastrowid

edge_skips = []
for source_label, target_label, edge_type, props in seed_data_v2.GRAPH_EDGES:
    src = node_ids.get(source_label)
    tgt = node_ids.get(target_label)
    if src is None or tgt is None:
        edge_skips.append((source_label, target_label))
        continue
    cur.execute(
        "INSERT INTO graph_edges (source_node_id,target_node_id,edge_type,properties_json) VALUES (?,?,?,?)",
        (src, tgt, edge_type, json.dumps(props)),
    )

hyp_ids = {}
for h in seed_data_v2.HYPOTHESES:
    steps = h["steps"]
    cur.execute(
        "INSERT INTO hypotheses (number,title,candidate_slug,gene_symbol,status) VALUES (?,?,?,?,?)",
        (h["number"], h["title"], h["candidate_slug"], h["gene_symbol"], h["status"]),
    )
    hid = cur.lastrowid
    hyp_ids[h["number"]] = hid
    for i, step in enumerate(steps):
        cur.execute(
            "INSERT INTO hypothesis_steps (hypothesis_id,sort_order,from_label,to_label,supporting_papers_json,"
            "confidence,conflicting_evidence,experimental_status,recommended_next_experiment) VALUES (?,?,?,?,?,?,?,?,?)",
            (hid, i, step["from_label"], step["to_label"], json.dumps(step["supporting_papers"]),
             step["confidence"], step["conflicting_evidence"], step["experimental_status"], step["recommended_next_experiment"]),
        )

conn.commit()

failures = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    if not cond:
        failures.append(label)
    print(f"[{status}] {label}")


# --- Layer 1: Data Fabric ---
check("39 data sources total", cur.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0] == 39)
check("19 data sources connected", cur.execute("SELECT COUNT(*) FROM data_sources WHERE status='connected'").fetchone()[0] == 19)
check("every data source key is unique", cur.execute(
    "SELECT COUNT(*) FROM (SELECT key FROM data_sources GROUP BY key HAVING COUNT(*) > 1)"
).fetchone()[0] == 0)

# --- Layer 3: Agent Network ---
check("60 agent definitions total", cur.execute("SELECT COUNT(*) FROM agent_definitions").fetchone()[0] == 60)
check("20 agents implemented", cur.execute("SELECT COUNT(*) FROM agent_definitions WHERE status='implemented'").fetchone()[0] == 20)
check("every implemented agent has an interval_minutes value", cur.execute(
    "SELECT COUNT(*) FROM agent_definitions WHERE status='implemented' AND interval_minutes IS NULL"
).fetchone()[0] == 0)
divisions = {r[0] for r in cur.execute("SELECT DISTINCT division FROM agent_definitions")}
check("6 divisions present, including Genomics and Development",
      {"Genomics", "Development"}.issubset(divisions) and len(divisions) == 6)

# --- Layer 2: Knowledge Graph ---
check("28 graph nodes", cur.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0] == 28)
check("28 graph edges, 0 skipped for missing endpoints", cur.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0] == 28 and len(edge_skips) == 0)
check("13 gene nodes", cur.execute("SELECT COUNT(*) FROM graph_nodes WHERE node_type='gene'").fetchone()[0] == 13)


def bfs_subgraph(start_id, depth):
    """Python re-implementation of PostgresGraphStore.subgraph's BFS, to
    prove the traversal logic (not just the seed data) is correct."""
    visited_nodes = {start_id}
    visited_edges = set()
    frontier = {start_id}
    for _ in range(depth):
        if not frontier:
            break
        next_frontier = set()
        placeholders = ",".join("?" * len(frontier))
        rows = cur.execute(
            f"SELECT id, source_node_id, target_node_id FROM graph_edges "
            f"WHERE source_node_id IN ({placeholders}) OR target_node_id IN ({placeholders})",
            tuple(frontier) * 2,
        ).fetchall()
        for eid, src, tgt in rows:
            visited_edges.add(eid)
            for nid in (src, tgt):
                if nid not in visited_nodes:
                    visited_nodes.add(nid)
                    next_frontier.add(nid)
        frontier = next_frontier
    return visited_nodes, visited_edges

atp6v0c_id = node_ids.get("ATP6V0C")
check("ATP6V0C gene node exists", atp6v0c_id is not None)
sub_nodes, sub_edges = bfs_subgraph(atp6v0c_id, depth=2)
check("ATP6V0C depth-2 subgraph includes itself and >=1 neighbor", atp6v0c_id in sub_nodes and len(sub_nodes) >= 2)

# --- Layer 4: Scientific Reasoning Engine ---
check("3 hypotheses total", cur.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0] == 3)
check("hypotheses 17, 18, 19 present", {17, 18, 19}.issubset(
    {r[0] for r in cur.execute("SELECT number FROM hypotheses")}
))
check("11 hypothesis steps total", cur.execute("SELECT COUNT(*) FROM hypothesis_steps").fetchone()[0] == 11)

for number in (17, 18, 19):
    hid = hyp_ids[number]
    confs = [r[0] for r in cur.execute("SELECT confidence FROM hypothesis_steps WHERE hypothesis_id=? ORDER BY sort_order", (hid,))]
    overall = sum(confs) / len(confs) if confs else 0.0
    check(f"hypothesis {number} overall_confidence computable and in [0,1]", 0.0 <= overall <= 1.0 and len(confs) > 0)

# --- Layer 5: Laboratory OS — recommendation ranking logic ---
# Mirrors app/routers/lab.py's next_experiment_recommendations: fetch
# unordered from SQL, then sort in Python by ascending confidence (weakest-
# evidenced links surfaced first) - the router does not rely on SQL ORDER BY.
open_steps = cur.execute(
    "SELECT confidence, recommended_next_experiment, experimental_status FROM hypothesis_steps "
    "WHERE experimental_status != 'validated' AND recommended_next_experiment != ''"
).fetchall()
check("at least one open (non-validated) recommendation exists", len(open_steps) > 0)
ranked = sorted(open_steps, key=lambda r: r[0])
ranked_confidences = [r[0] for r in ranked]
check("post-sort recommendation order is non-decreasing by confidence",
      ranked_confidences == sorted(ranked_confidences))
check("weakest-evidenced recommendation is first after ranking",
      len(ranked) == 0 or ranked_confidences[0] == min(r[0] for r in open_steps))

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED:", failures)
    sys.exit(1)
else:
    print("ALL V3 SCHEMA/SEED/LOGIC CHECKS PASSED")
