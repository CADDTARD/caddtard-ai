# CADDTARD AI v3.1 MVP

Computer-Aided Drug Design Targeting Rare Disease — V-ATPase loss-of-function program.

v2.0 extends the v1.0 deployable foundation into the full six-layer architecture:
Data Fabric (Layer 1), Scientific Knowledge Graph (Layer 2), AI Agent Network
(Layer 3), Scientific Reasoning Engine (Layer 4), Laboratory Operating System
(Layer 5), and Executive Dashboard (Layer 6). **Read [ARCHITECTURE.md](./ARCHITECTURE.md)
first** — it maps every item in the target architecture to implemented / scaffolded /
planned, with exact counts, so you know precisely what's real before you build on it.
**New in v3.0:** 8 more real-live-data agents (20 total, up from 12) and a new
operational layer — CRO/vendor registry, sample chain-of-custody, assay acceptance,
cost tracking, and go/no-go governance — importable via CSV, never fabricated.
See the "v3.0 operational layer" section below and `ARCHITECTURE.md`'s Layer 7.
**New in v3.1 MVP:** the dashboard health-path defect is fixed, the operational
layer is visible in the dashboard, Alembic owns database migrations, readiness
verifies the database plus all expected scheduler jobs, startup seeding is
transaction-safe, and CI tests SQLite, PostgreSQL, and the production image.
**Want this actually running on the internet, not just in this repo?** See
[DEPLOY.md](./DEPLOY.md).

## What changed vs. v1.0

| v1.0 | v2.0 |
|---|---|
| 4 scheduled agents, hardcoded intervals | 52-agent taxonomy across 5 divisions, DB-seeded; 12 implemented and scheduled, 40 reserved (`GET /api/agents?division=&status=`) |
| No source registry | 33-source Layer 1 registry, 12 marked `connected` (`GET /api/sources`) |
| No knowledge graph | Relational graph (Postgres/SQLite today, Neo4j-swappable) — 28 nodes, 28 edges (`GET /api/graph/...`) |
| No structured reasoning | 3 evidence-graded hypothesis chains, 11 steps, each with confidence/citations/next-experiment (`GET /api/hypotheses`) |
| No lab tracking | Full experiment/protocol/reagent/notebook/assay CRUD + AI-recommended next experiments (`GET/POST /api/lab/...`) |
| No portfolio view | Executive dashboard aggregating all layers per candidate (`GET /api/dashboard/health`) |

## What changed vs. the original static-HTML prototypes

| Prototype | v1.0+ |
|---|---|
| Data embedded as inline JSON in the HTML | Persisted in SQLite (local) or Postgres (Docker) |
| "Live" agents ran in the *browser*, blocked by CORS on some sources | Agents run *server-side* on a schedule (APScheduler), no CORS exposure |
| Regulatory checklist saved to `localStorage` (one browser, one machine) | Checklist persisted server-side via `/api/checklist`, shared across every client |
| Open `file://...html` directly | Run `docker compose up`, open `http://localhost:8000/` |
| No health checks, no process supervision | `/health`, `/health/ready`, Docker `HEALTHCHECK`, compose `depends_on: condition: service_healthy` |

## Architecture

```
caddtard-ai/
├── app/
│   ├── main.py            FastAPI app: routers, CORS, lifespan (seed + scheduler)
│   ├── config.py          Settings from environment variables (.env supported)
│   ├── database.py        SQLAlchemy engine/session, works against SQLite or Postgres
│   ├── models.py          ORM schema: v1 tables (Gene, Variant, ScoringCandidate,
│   │                      Candidate, TimelineItem, CostItem, CostSummary,
│   │                      ChecklistItem, AgentRun) + v2 tables (DataSource, GraphNode,
│   │                      GraphEdge, AgentDefinition, Hypothesis, HypothesisStep,
│   │                      Experiment, Protocol, ReagentItem, NotebookEntry, AssayResult)
│   ├── schemas.py         Pydantic response contracts (auto-documented at /docs)
│   ├── seed_data.py       v1 research dataset (13 genes, 60 variants, 10 scored
│   │                      programs, 3 selected candidates)
│   ├── seed_data_v2.py    v2 dataset: 33 data sources, 52 agent definitions,
│   │                      28 graph nodes / 28 edges, 3 hypothesis chains (11 steps)
│   ├── seed.py            Idempotent seeding for both v1 and v2 tables, runs on startup
│   ├── graph/store.py     GraphStore interface + PostgresGraphStore (Neo4j swap-in ready)
│   ├── routers/           health, genes, variants, scoring, candidates, checklist,
│   │                      agents, sources, graph, hypotheses, lab, dashboard
│   ├── agents/            20 implemented agents across 6 divisions + APScheduler wiring
│   ├── models_ops.py      v3.0 operational layer: CRO/vendor, studies, samples,
│   │                      assay acceptance, costs, go/no-go, readiness ledger
│   ├── ops_logic.py       Pure evaluation functions (no SQLAlchemy dependency)
│   ├── ops_import.py      CSV import - never fabricates a value for a missing column
│   └── static/            The dashboard (plain HTML/CSS/JS + Cytoscape.js via CDN)
├── import_templates/      8 CSV templates for the operational layer (CRO vendors,
│                          quotes, samples, assay acceptance, costs, CMC/nonclinical/
│                          regulatory readiness)
├── tests/                 pytest suite (health + full API surface + ops logic)
├── ARCHITECTURE.md        Full implemented/scaffolded/planned map for the 6-layer spec
├── Dockerfile
├── docker-compose.yml     api + postgres (required) + neo4j/redis/opensearch
│                          (optional, `--profile extended`), all with healthchecks
└── requirements.txt
```

## Run it

### Option A — Docker Compose (recommended, matches production topology)

```bash
docker compose up --build
```

- API + dashboard: http://localhost:8000/
- Interactive API docs: http://localhost:8000/docs
- Postgres is provisioned automatically with a named volume (`caddtard_pgdata`) for
  persistence across restarts.
- The `api` service will not report healthy until `db` passes its own healthcheck
  (`pg_isready`), and `api`'s own healthcheck hits `/health/ready`.

Stop with `docker compose down` (add `-v` to also drop the Postgres volume).

### Option B — local Python, no Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

With no `DATABASE_URL` set, this defaults to a local SQLite file (`./caddtard.db`) —
zero extra setup. Copy `.env.example` to `.env` to override any setting.

### Run the tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

Tests run against an isolated temporary SQLite database and disable the scheduler
(`AGENTS_ENABLED=false`) so they don't depend on a live network connection; the one
test that triggers a real agent run (`test_agent_manual_trigger_records_a_run`)
asserts that a run is recorded whether or not the outbound call to UniProt actually
succeeds, so it's safe to run offline too.

## API surface

Full interactive reference at `/docs` once running. Summary:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe, no dependencies |
| `GET /health/ready` | Readiness probe — checks DB connectivity, scheduler state, and registered-vs-expected job count; returns 503 if not ready |
| `GET /api/genes?top3_only=&status=` | The 13-gene verified reference table |
| `GET /api/genes/{symbol}` | One gene + its variants |
| `GET /api/variants?gene=` | Variant-level rows from the originally uploaded LOF data.xlsx |
| `GET /api/scoring` | Full 10-program prioritization rubric, sorted by composite score |
| `GET /api/candidates` | The 3 selected programs |
| `GET /api/candidates/{slug}` | Full profile + timeline + cost breakdown for one candidate (`drta`, `atp6v0c`, `tcirg1`) |
| `GET /api/checklist?candidate=` | IND-readiness checklist state |
| `PATCH /api/checklist/{id}` | Toggle a checklist item |
| `GET /api/agents?division=&status=` | Full ~52-agent taxonomy, filterable; `implemented` rows include their last run |
| `GET /api/agents/divisions` | The 6 division names |
| `GET /api/agents/{key}/runs` | Run history for one agent |
| `GET /api/agents/{key}/latest` | Most recent run, including full detail JSON |
| `POST /api/agents/{key}/run` | Trigger an implemented agent immediately (background task, 202 Accepted; 409 if still `planned`) |
| `GET /api/sources?status=&category=` | Layer 1 data-source registry |
| `GET /api/graph/nodes?node_type=` | Layer 2 knowledge-graph nodes |
| `GET /api/graph/nodes/{id}/subgraph?depth=` | BFS subgraph around one node |
| `GET /api/graph/genes/{symbol}/subgraph?depth=` | Subgraph lookup by gene symbol |
| `GET /api/hypotheses?candidate=&gene=` | Layer 4 evidence-graded hypothesis chains |
| `GET /api/hypotheses/{number}` | One hypothesis chain in full |
| `GET/POST /api/lab/experiments` | Layer 5 experiment log |
| `PATCH /api/lab/experiments/{id}` | Update experiment status/owner/objective |
| `POST/GET /api/lab/experiments/{id}/protocols`, `/notebook`, `/results` | Protocol, notebook, and assay-result records per experiment |
| `GET/POST /api/lab/reagents?low_stock_only=` | Reagent inventory |
| `GET /api/lab/recommendations?candidate=` | AI-recommended next experiments, traced back to Layer 4 |
| `GET /api/dashboard/health/{slug}` | Layer 6 project health for one candidate |
| `GET /api/dashboard/health` | Portfolio health for all 3 candidates |
| `GET/POST /api/ops/vendors`, `/api/ops/vendors/import` | CRO vendor registry (CSV import only - never invented) |
| `POST /api/ops/quotes/import`, `GET /api/ops/quotes/compare?study_type=` | Vendor quote import + price comparison |
| `GET/POST /api/ops/studies` | Operational study registry |
| `POST /api/ops/studies/{id}/samples/import`, `/custody-events` | Sample inventory + chain of custody |
| `POST /api/ops/studies/{id}/assay-acceptance/import` | Prospective acceptance criteria + auto-evaluation against measured results |
| `POST /api/ops/studies/{id}/costs/import`, `GET .../cost-summary` | Cost tracking + variance |
| `POST /api/ops/studies/{id}/go-no-go/compute`, `POST /api/ops/go-no-go/{id}/review` | System-proposed go/no-go + required human review |
| `POST /api/ops/readiness/{category}/import`, `GET /api/ops/readiness/{slug}` | CMC/nonclinical/regulatory readiness ledger |
| `GET /api/ops/summary` | Dashboard payload for vendor, study, and evidence-readiness oversight |

## The 20 implemented agents

Each runs on an independent interval (seeded on `AgentDefinition.interval_minutes`,
overridable via `.env`'s `DEFAULT_AGENT_INTERVAL_MINUTES` for unset rows), calls a
public source directly from the server, and writes an `AgentRun` row (status,
summary, timestamped detail JSON) whether it succeeds or fails — a failed outbound
call never crashes the scheduler. See `ARCHITECTURE.md` for the full 60-agent
taxonomy, including the 40 not yet implemented.

**Evidence & Infrastructure** — `literature` (PubMed/NCBI E-utilities), `structural`
(RCSB PDB), `ontology` (EBI QuickGO), `github_watch` (GitHub Search API),
`europepmc_literature` (Europe PMC, v3.0).
**Genomics** — `genomics` (UniProt), `gene_transcript` (Ensembl, ID resolved
dynamically by symbol), `population_genetics` (gnomAD GraphQL),
`pathway_intelligence` (Reactome, v3.0).
**Disease Biology** — `disease_phenotype` (Monarch Initiative), `who_burden`
(WHO Global Health Observatory, v3.0).
**Therapeutics** — `small_molecule` (ChEMBL), `compound_properties` (PubChem, v3.0).
**AI Science** — `structure_prediction` (AlphaFold DB).
**Development** — `clinical_trials` (ClinicalTrials.gov v2), `competitive_intelligence`
(Open Targets Platform GraphQL), `regulatory_precedent` (openFDA, v3.0),
`cmc_product_label` (DailyMed, v3.0), `funding_opportunities` (NIH RePORTER, v3.0),
`patent_landscape` (PatentsView, v3.0 — requires a free API key, see `.env.example`).

## v3.0 operational layer, in one paragraph

CRO/vendor data, quotes, sample records, and CMC/nonclinical/regulatory readiness
evidence have no public live API — nobody publishes a real-time feed of what a
contract lab will charge you. So unlike the 20 agents above, this layer is
import-then-score: you feed it verified CSVs (`import_templates/*.csv`), and only
the *evaluation* (assay pass/fail, cost variance, go/no-go) is computed, from data
already on file, never invented at evaluation time. The go/no-go engine explicitly
returns `insufficient_data` — not a confident-looking `go` — when no measured
evidence exists yet; a human still has to approve, reject, or defer every
recommendation (`POST /api/ops/go-no-go/{id}/review`). One demo study
(`is_demo=True`, everything labeled `DEMO_SEED`) is seeded end to end so you can
see the whole pipeline work without mistaking it for real data. Full write-up:
`ARCHITECTURE.md` Layer 7.

## Known limitations / honest notes

- **See `ARCHITECTURE.md` for the full layer-by-layer implemented/scaffolded/planned
  map** — the short version: 20 of 60 taxonomy agents are implemented, 19 of 39
  registered data sources are connected, the knowledge graph runs on Postgres with a
  documented Neo4j swap-in path, the v3.0 operational layer is import-then-score by
  design (no live external source for CRO/CMC data exists), and there is no
  React/Next.js/GraphQL/Kubernetes/ML layer in this build (the REST API and
  dashboard are complete and don't require one to be useful).
- The v3.1 MVP has been executed locally with its pinned dependencies: the FastAPI
  suite passes 60 tests, the initial Alembic migration upgrades a clean database
  with no pending schema operations, and all three standalone schema/logic checks
  pass. CI repeats the suite on SQLite and PostgreSQL and builds the production
  image. A live host deployment remains the final infrastructure proof point.
- The prioritization scores in `/api/scoring` are the same qualitative,
  expert-judgment rubric from the prior report — not a licensed market-sizing model.
- The `open_high_risk_flags` count in `/api/dashboard/health` is a small static
  lookup (`KNOWN_RISK_FLAG_COUNT` in `app/routers/dashboard.py`), documented and
  traceable to the prior report's risk section — not parsed from free text.
- Default demo credentials (`caddtard`/`caddtard`, and `neo4j`/`caddtard_dev` for the
  optional Neo4j service) are set in `docker-compose.yml` for local development only.
  Change them (and set real secrets) before deploying anywhere reachable from the
  internet.
- CORS defaults to `localhost:8000`/`127.0.0.1:8000`. Update `CORS_ORIGINS` before
  hosting the dashboard on a different origin than the API.
