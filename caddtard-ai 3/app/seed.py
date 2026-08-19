"""
Idempotent database seeding. Runs automatically on startup (see main.py) and
can also be run standalone: `python -m app.seed`.
"""
import json
import logging

from sqlalchemy.orm import Session

from app import seed_data, seed_data_v2, seed_data_v3
from app.database import Base, SessionLocal, engine
from app.graph.store import PostgresGraphStore
from app.models import (
    AgentDefinition,
    Candidate,
    ChecklistItem,
    CostItem,
    CostSummary,
    DataSource,
    Gene,
    Hypothesis,
    HypothesisStep,
    ScoringCandidate,
    TimelineItem,
    Variant,
)
from app.models_ops import CroVendor, ReadinessRequirement, Study  # noqa: F401 - import registers tables on Base.metadata
from app.ops_import import (
    import_assay_acceptance,
    import_cro_vendors,
    import_readiness,
    import_samples,
    import_study_costs,
    import_vendor_quotes,
)

logger = logging.getLogger("caddtard.seed")


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed(db)
        _seed_v2(db)  # independent idempotency check - runs even if v1 tables were already seeded by an older deploy
        _seed_v3(db)  # operational layer: readiness ledger + one clearly-labeled demo study
    finally:
        db.close()


def _seed(db: Session) -> None:
    if db.query(Gene).count() > 0:
        logger.info("v1 tables already seeded, skipping.")
        return

    logger.info("Seeding database with CADDTARD AI reference dataset...")

    gene_by_symbol: dict[str, Gene] = {}
    for g in seed_data.GENES:
        gene = Gene(**g)
        db.add(gene)
        gene_by_symbol[g["symbol"]] = gene
    db.flush()  # assigns primary keys before variants reference them

    for v in seed_data.VARIANTS:
        gene = gene_by_symbol.get(v["gene_symbol"])
        if gene is None:
            continue
        db.add(Variant(gene_id=gene.id, **{k: val for k, val in v.items() if k != "gene_symbol"}))

    for s in seed_data.SCORING:
        db.add(ScoringCandidate(**s))

    candidate_by_slug: dict[str, Candidate] = {}
    for c in seed_data.CANDIDATES:
        candidate = Candidate(**c)
        db.add(candidate)
        candidate_by_slug[c["slug"]] = candidate
    db.flush()

    for slug, items in seed_data.TIMELINE.items():
        candidate = candidate_by_slug.get(slug)
        if candidate is None:
            continue
        for item in items:
            db.add(TimelineItem(candidate_id=candidate.id, **item))

    for slug, items in seed_data.COST_ITEMS.items():
        candidate = candidate_by_slug.get(slug)
        if candidate is None:
            continue
        for item in items:
            db.add(CostItem(candidate_id=candidate.id, **item))

    for slug, summary in seed_data.COST_SUMMARY.items():
        db.add(CostSummary(candidate_slug=slug, **summary))

    for slug in list(candidate_by_slug.keys()) + ["global"]:
        for item in seed_data.CHECKLIST_DEFAULTS:
            db.add(ChecklistItem(candidate_slug=slug, **item))

    db.commit()
    logger.info(
        "Seed complete: %d genes, %d variants, %d scoring rows, %d candidates.",
        len(seed_data.GENES), len(seed_data.VARIANTS), len(seed_data.SCORING), len(seed_data.CANDIDATES),
    )


def _seed_v2(db: Session) -> None:
    """Layers 1/2/3/4: data source registry, knowledge graph, agent
    taxonomy, and reasoning-engine hypotheses. Independent idempotency check
    (keyed on DataSource, not Gene) so this still runs against a database
    that was seeded by v1 code before these tables existed."""
    if db.query(DataSource).count() > 0:
        logger.info("v2 tables already seeded, skipping.")
        return

    logger.info("Seeding v2 layers (data fabric, knowledge graph, agent taxonomy, hypotheses)...")

    for s in seed_data_v2.DATA_SOURCES:
        db.add(DataSource(**s))

    for a in seed_data_v2.AGENT_DEFINITIONS:
        db.add(AgentDefinition(**a))

    graph = PostgresGraphStore(db)
    node_by_label: dict[str, int] = {}
    for n in seed_data_v2.GRAPH_NODES:
        node = graph.upsert_node(n["node_type"], n["label"], n.get("external_ref", ""), n.get("properties"))
        node_by_label[n["label"]] = node.id
    db.flush()

    edge_count = 0
    for source_label, target_label, edge_type, props in seed_data_v2.GRAPH_EDGES:
        src_id = node_by_label.get(source_label)
        tgt_id = node_by_label.get(target_label)
        if src_id is None or tgt_id is None:
            logger.warning("Graph edge references unknown node(s): %r -> %r", source_label, target_label)
            continue
        graph.upsert_edge(src_id, tgt_id, edge_type, props)
        edge_count += 1

    hyp_count = 0
    step_count = 0
    for h in seed_data_v2.HYPOTHESES:
        steps = h.pop("steps")
        hypothesis = Hypothesis(**h)
        db.add(hypothesis)
        db.flush()
        for i, step in enumerate(steps):
            papers = step.pop("supporting_papers")
            db.add(HypothesisStep(
                hypothesis_id=hypothesis.id,
                sort_order=i,
                supporting_papers_json=json.dumps(papers),
                **step,
            ))
            step_count += 1
        hyp_count += 1

    db.commit()
    logger.info(
        "v2 seed complete: %d data sources, %d agent definitions, %d graph nodes, %d graph edges, %d hypotheses (%d steps).",
        len(seed_data_v2.DATA_SOURCES), len(seed_data_v2.AGENT_DEFINITIONS),
        len(node_by_label), edge_count, hyp_count, step_count,
    )


def _seed_v3(db: Session) -> None:
    """Operational layer: CMC/nonclinical/regulatory readiness ledger for the
    two real repurposing candidates, plus one demo study imported through the
    exact same import_* functions the API exposes (see app/ops_import.py) -
    not a separate hand-rolled seeding path - so this seed is itself a test
    that the import pipeline works, not just a fixture."""
    if db.query(ReadinessRequirement).count() > 0:
        logger.info("v3 operational layer already seeded, skipping.")
        return

    logger.info("Seeding v3 operational layer (readiness ledger + demo study)...")

    for r in seed_data_v3.READINESS_REQUIREMENTS:
        db.add(ReadinessRequirement(**r))
    db.commit()

    vendors = import_cro_vendors(db, seed_data_v3.DEMO_VENDOR_CSV, "DEMO_SEED")
    db.commit()
    name_map = {v.name: v.id for v in vendors}
    import_vendor_quotes(db, seed_data_v3.DEMO_QUOTE_CSV, "DEMO_SEED", name_map)

    study = Study(
        title="DEMO STUDY - not real - proves CRO/sample/assay/cost/go-no-go pipeline",
        candidate_slug="auranofin-cbm",
        study_type="murine efficacy model",
        cro_vendor_id=vendors[0].id if vendors else None,
        owner="DEMO_SEED",
        status="active",
        is_demo=True,
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    import_samples(db, seed_data_v3.DEMO_SAMPLE_CSV, "DEMO_SEED", study.id)
    import_assay_acceptance(db, seed_data_v3.DEMO_ASSAY_CSV, "DEMO_SEED", study.id)
    import_study_costs(db, seed_data_v3.DEMO_COST_CSV, "DEMO_SEED", study.id)
    db.commit()

    logger.info(
        "v3 seed complete: %d readiness requirements, 1 demo vendor, 1 demo study (id=%d, is_demo=True).",
        len(seed_data_v3.READINESS_REQUIREMENTS), study.id,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()
