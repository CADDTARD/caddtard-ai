"""
Persistent schema. Everything the two prior static dashboards embedded as
inline JSON now lives here, queried live through the API instead.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Gene(Base):
    __tablename__ = "genes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    uniprot_accession: Mapped[str] = mapped_column(String(16))
    protein_name: Mapped[str] = mapped_column(String(256))
    subunit_role: Mapped[str] = mapped_column(String(256), default="")
    organ_system: Mapped[str] = mapped_column(String(256), default="")
    inheritance: Mapped[str] = mapped_column(String(128), default="")
    omim: Mapped[str] = mapped_column(String(256), default="")
    disease: Mapped[str] = mapped_column(Text, default="")
    mechanism: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="confirmed")
    verification_note: Mapped[str] = mapped_column(Text, default="")
    source_citation: Mapped[str] = mapped_column(String(512), default="")
    source_url: Mapped[str] = mapped_column(String(512), default="")
    in_top3: Mapped[bool] = mapped_column(Boolean, default=False)
    xlsx_uniprot_claim: Mapped[str] = mapped_column(String(32), default="")

    variants: Mapped[list["Variant"]] = relationship(back_populates="gene", cascade="all, delete-orphan")


class Variant(Base):
    """One row per variant from the originally uploaded LOF data.xlsx."""

    __tablename__ = "variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gene_id: Mapped[int] = mapped_column(ForeignKey("genes.id"))
    mutation: Mapped[str] = mapped_column(String(32))
    wt_aa: Mapped[str] = mapped_column(String(4))
    mut_aa: Mapped[str] = mapped_column(String(4))
    position: Mapped[int] = mapped_column(Integer)
    phenotype_severity: Mapped[str] = mapped_column(String(32), default="")
    mechanism_class: Mapped[str] = mapped_column(String(64), default="")
    degradation_risk: Mapped[str] = mapped_column(String(32), default="")
    conservation_score: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_delta_g: Mapped[float] = mapped_column(Float, default=0.0)
    structural_region: Mapped[str] = mapped_column(String(64), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(256), default="")

    gene: Mapped["Gene"] = relationship(back_populates="variants")


class ScoringCandidate(Base):
    """Prioritization rubric row (10 programs scored, 3 selected)."""

    __tablename__ = "scoring_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program: Mapped[str] = mapped_column(String(256))
    genes: Mapped[str] = mapped_column(String(128))  # comma-separated symbols
    commercial: Mapped[float] = mapped_column(Float)
    patients: Mapped[float] = mapped_column(Float)
    cmc: Mapped[float] = mapped_column(Float)
    feasibility: Mapped[float] = mapped_column(Float)
    composite: Mapped[float] = mapped_column(Float)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str] = mapped_column(Text, default="")


class Candidate(Base):
    """Deep-dive profile for each of the top-3 selected programs."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    genes: Mapped[str] = mapped_column(String(128))
    uniprot: Mapped[str] = mapped_column(String(128), default="")
    organ: Mapped[str] = mapped_column(String(256), default="")
    inheritance: Mapped[str] = mapped_column(String(128), default="")
    omim: Mapped[str] = mapped_column(String(256), default="")
    mechanism: Mapped[str] = mapped_column(Text, default="")
    soc: Mapped[str] = mapped_column(Text, default="")
    modality: Mapped[str] = mapped_column(Text, default="")
    biomarkers: Mapped[str] = mapped_column(Text, default="")
    commercial_precedent: Mapped[str] = mapped_column(Text, default="")
    risks: Mapped[str] = mapped_column(Text, default="")

    timeline_items: Mapped[list["TimelineItem"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    cost_items: Mapped[list["CostItem"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class TimelineItem(Base):
    __tablename__ = "timeline_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    month_label: Mapped[str] = mapped_column(String(32))
    track: Mapped[str] = mapped_column(String(128))
    detail: Mapped[str] = mapped_column(Text)

    candidate: Mapped["Candidate"] = relationship(back_populates="timeline_items")


class CostItem(Base):
    """Line-item non-clinical cost estimate; empty for candidates priced only all-in."""

    __tablename__ = "cost_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    name: Mapped[str] = mapped_column(String(256))
    low_usd_k: Mapped[float] = mapped_column(Float)
    high_usd_k: Mapped[float] = mapped_column(Float)
    optional: Mapped[bool] = mapped_column(Boolean, default=False)

    candidate: Mapped["Candidate"] = relationship(back_populates="cost_items")


class CostSummary(Base):
    """All-in program-level range + narrative note + source, one per candidate."""

    __tablename__ = "cost_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_slug: Mapped[str] = mapped_column(String(32), unique=True)
    allin_low_usd_k: Mapped[float] = mapped_column(Float)
    allin_high_usd_k: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="")


class ChecklistItem(Base):
    """IND-readiness checklist. Persisted server-side (replaces browser localStorage)."""

    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_slug: Mapped[str] = mapped_column(String(32), default="global")
    category: Mapped[str] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(String(256))
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AgentRun(Base):
    """Every execution of a scheduled or manually-triggered agent, for audit/history."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|success|error
    trigger: Mapped[str] = mapped_column(String(16), default="scheduled")  # scheduled|manual
    summary: Mapped[str] = mapped_column(Text, default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")


# ---------------------------------------------------------------------------
# Layer 1 - Data Fabric: registry of every external/internal source the
# platform is designed to ingest from. "connected" means a real agent in
# app/agents/ calls it live; "planned" means the interface is reserved but
# not yet implemented (most require an API key, a data license, or don't
# exist yet for this project, e.g. internal LIMS/ELN).
# ---------------------------------------------------------------------------
class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))  # genomics|literature|structure|chemistry|clinical|internal|...
    integration_type: Mapped[str] = mapped_column(String(32), default="rest_api")  # rest_api|graphql|internal|file
    status: Mapped[str] = mapped_column(String(16), default="planned")  # connected|planned
    agent_key: Mapped[str] = mapped_column(String(64), default="")  # which agent implements this, if any
    url: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(Text, default="")


# ---------------------------------------------------------------------------
# Layer 2 - Scientific Knowledge Graph. Modeled relationally (nodes/edges
# tables) so it is fully queryable and testable with only Postgres/SQLite.
# The API talks to a small GraphStore interface (app/graph/store.py), not
# directly to these tables, so swapping in a native graph database (Neo4j is
# the documented v2 target - see ARCHITECTURE.md) only requires a new adapter
# behind that interface, not a rewrite of the routers or the frontend.
# ---------------------------------------------------------------------------
class GraphNode(Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (UniqueConstraint("node_type", "external_ref", name="uq_node_type_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_type: Mapped[str] = mapped_column(String(32), index=True)  # gene|variant|protein|pathway|disease|phenotype|drug|...
    label: Mapped[str] = mapped_column(String(256))
    # NULL (not "") when unset - multiple nodes of the same node_type with no
    # external ref yet (e.g. internally-tracked drug candidates) must not
    # collide under uq_node_type_ref below; SQL treats distinct NULLs as
    # non-duplicate but would reject a second identical "" value.
    external_ref: Mapped[str | None] = mapped_column(String(128), default=None, nullable=True)  # e.g. "UniProt:P38606"
    properties_json: Mapped[str] = mapped_column(Text, default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_node_id: Mapped[int] = mapped_column(ForeignKey("graph_nodes.id"))
    target_node_id: Mapped[int] = mapped_column(ForeignKey("graph_nodes.id"))
    edge_type: Mapped[str] = mapped_column(String(48), index=True)  # activates|inhibits|binds|pathogenic_for|causes|...
    properties_json: Mapped[str] = mapped_column(Text, default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    source_node: Mapped["GraphNode"] = relationship(foreign_keys=[source_node_id])
    target_node: Mapped["GraphNode"] = relationship(foreign_keys=[target_node_id])


# ---------------------------------------------------------------------------
# Layer 3 - AI Agent Network, promoted from a hardcoded Python list (v1) to a
# real table so the ~100-agent taxonomy from the architecture spec is
# queryable/filterable by division and status through the API itself.
# ---------------------------------------------------------------------------
class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    division: Mapped[str] = mapped_column(String(64), index=True)  # Genomics|Disease Biology|Therapeutics|AI Science|Development
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="planned")  # implemented|planned
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    module_path: Mapped[str] = mapped_column(String(128), default="")  # e.g. app.agents.genomics_agent, blank if planned


# ---------------------------------------------------------------------------
# Layer 4 - Scientific Reasoning Engine: explicit, evidence-graded hypothesis
# chains (matches the "Hypothesis 17" example in the architecture spec).
# ---------------------------------------------------------------------------
class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(256))
    candidate_slug: Mapped[str] = mapped_column(String(32), default="")
    gene_symbol: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(24), default="active")  # active|supported|refuted|retired
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    steps: Mapped[list["HypothesisStep"]] = relationship(back_populates="hypothesis", cascade="all, delete-orphan")


class HypothesisStep(Base):
    """One causal edge in a hypothesis chain, e.g.
    'decreased lysosomal acidification' -> 'autophagy failure'."""

    __tablename__ = "hypothesis_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(ForeignKey("hypotheses.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    from_label: Mapped[str] = mapped_column(String(256))
    to_label: Mapped[str] = mapped_column(String(256))
    supporting_papers_json: Mapped[str] = mapped_column(Text, default="[]")  # [{"title":..,"url":..}]
    confidence: Mapped[float] = mapped_column(Float, default=0.5)  # 0-1
    conflicting_evidence: Mapped[str] = mapped_column(Text, default="")
    experimental_status: Mapped[str] = mapped_column(String(24), default="not_started")  # not_started|in_progress|validated|refuted
    recommended_next_experiment: Mapped[str] = mapped_column(Text, default="")

    hypothesis: Mapped["Hypothesis"] = relationship(back_populates="steps")


# ---------------------------------------------------------------------------
# Layer 5 - Laboratory Operating System.
# ---------------------------------------------------------------------------
class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    candidate_slug: Mapped[str] = mapped_column(String(32), default="")
    hypothesis_id: Mapped[int | None] = mapped_column(ForeignKey("hypotheses.id"), nullable=True)
    objective: Mapped[str] = mapped_column(Text, default="")
    assay_type: Mapped[str] = mapped_column(String(32), default="other")  # sequencing|microscopy|flow_cytometry|elisa|western_blot|lc_ms|animal_study|other
    status: Mapped[str] = mapped_column(String(24), default="planned")  # planned|in_progress|completed|blocked
    owner: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    protocols: Mapped[list["Protocol"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    notebook_entries: Mapped[list["NotebookEntry"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    assay_results: Mapped[list["AssayResult"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")


class Protocol(Base):
    __tablename__ = "protocols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"))
    title: Mapped[str] = mapped_column(String(256))
    version: Mapped[str] = mapped_column(String(16), default="v1")
    body_markdown: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    experiment: Mapped["Experiment"] = relationship(back_populates="protocols")


class ReagentItem(Base):
    __tablename__ = "reagent_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    catalog_number: Mapped[str] = mapped_column(String(64), default="")
    vendor: Mapped[str] = mapped_column(String(128), default="")
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(32), default="")
    location: Mapped[str] = mapped_column(String(128), default="")
    reorder_threshold: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class NotebookEntry(Base):
    __tablename__ = "notebook_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"))
    author: Mapped[str] = mapped_column(String(128), default="")
    entry_date: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    experiment: Mapped["Experiment"] = relationship(back_populates="notebook_entries")


class AssayResult(Base):
    __tablename__ = "assay_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"))
    assay_type: Mapped[str] = mapped_column(String(32), default="other")
    summary: Mapped[str] = mapped_column(Text, default="")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    file_ref: Mapped[str] = mapped_column(String(512), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    experiment: Mapped["Experiment"] = relationship(back_populates="assay_results")
