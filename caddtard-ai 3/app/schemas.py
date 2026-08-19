"""Pydantic response/request models — these define the public API contract
that shows up automatically in /docs (Swagger) and /redoc."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mutation: str
    wt_aa: str
    mut_aa: str
    position: int
    phenotype_severity: str
    mechanism_class: str
    degradation_risk: str
    conservation_score: float
    predicted_delta_g: float
    structural_region: str
    confidence: float
    source: str


class GeneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    uniprot_accession: str
    protein_name: str
    subunit_role: str
    organ_system: str
    inheritance: str
    omim: str
    disease: str
    mechanism: str
    status: str
    verification_note: str
    source_citation: str
    source_url: str
    in_top3: bool
    xlsx_uniprot_claim: str


class GeneWithVariants(GeneOut):
    variants: list[VariantOut] = []


class ScoringOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    program: str
    genes: str
    commercial: float
    patients: float
    cmc: float
    feasibility: float
    composite: float
    selected: bool
    rationale: str


class TimelineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    month_label: str
    track: str
    detail: str
    sort_order: int


class CostItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    low_usd_k: float
    high_usd_k: float
    optional: bool


class CostSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    allin_low_usd_k: float
    allin_high_usd_k: float
    note: str
    source: str


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    genes: str
    uniprot: str
    organ: str
    inheritance: str
    omim: str
    mechanism: str
    soc: str
    modality: str
    biomarkers: str
    commercial_precedent: str
    risks: str


class CandidateDetailOut(CandidateOut):
    timeline: list[TimelineItemOut] = []
    cost_items: list[CostItemOut] = []
    cost_summary: CostSummaryOut | None = None


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    candidate_slug: str
    category: str
    label: str
    checked: bool
    sort_order: int
    updated_at: datetime


class ChecklistToggleIn(BaseModel):
    checked: bool


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    agent_name: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    trigger: str
    summary: str


class AgentRunDetailOut(AgentRunOut):
    detail_json: str


class AgentDefinitionOut(BaseModel):
    key: str
    name: str
    division: str
    description: str
    status: str  # implemented | planned
    interval_minutes: int | None = None
    last_run: AgentRunOut | None = None


class HealthOut(BaseModel):
    status: str
    app: str
    version: str


class ReadinessOut(BaseModel):
    status: str
    database: bool
    scheduler_running: bool


# --- Layer 1: Data Fabric ---
class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    name: str
    category: str
    integration_type: str
    status: str  # connected | planned
    agent_key: str
    url: str
    description: str


# --- Layer 2: Knowledge Graph ---
class GraphNodeOut(BaseModel):
    id: int
    node_type: str
    label: str
    external_ref: str
    properties: dict = {}


class GraphEdgeOut(BaseModel):
    id: int
    source_id: int
    target_id: int
    edge_type: str
    properties: dict = {}


class SubgraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


# --- Layer 4: Scientific Reasoning Engine ---
class SupportingPaper(BaseModel):
    title: str
    url: str = ""


class HypothesisStepOut(BaseModel):
    id: int
    sort_order: int
    from_label: str
    to_label: str
    supporting_papers: list[SupportingPaper] = []
    confidence: float
    conflicting_evidence: str
    experimental_status: str
    recommended_next_experiment: str


class HypothesisOut(BaseModel):
    id: int
    number: int
    title: str
    candidate_slug: str
    gene_symbol: str
    status: str
    overall_confidence: float
    steps: list[HypothesisStepOut] = []


# --- Layer 5: Laboratory Operating System ---
class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    candidate_slug: str
    hypothesis_id: int | None
    objective: str
    assay_type: str
    status: str
    owner: str
    created_at: datetime
    updated_at: datetime


class ExperimentCreate(BaseModel):
    title: str
    candidate_slug: str = ""
    hypothesis_id: int | None = None
    objective: str = ""
    assay_type: str = "other"
    status: str = "planned"
    owner: str = ""


class ExperimentUpdate(BaseModel):
    status: str | None = None
    objective: str | None = None
    owner: str | None = None


class ProtocolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    experiment_id: int
    title: str
    version: str
    body_markdown: str
    created_at: datetime


class ProtocolCreate(BaseModel):
    title: str
    version: str = "v1"
    body_markdown: str = ""


class ReagentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    catalog_number: str
    vendor: str
    quantity: float
    unit: str
    location: str
    reorder_threshold: float
    updated_at: datetime


class ReagentItemCreate(BaseModel):
    name: str
    catalog_number: str = ""
    vendor: str = ""
    quantity: float = 0.0
    unit: str = ""
    location: str = ""
    reorder_threshold: float = 0.0


class NotebookEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    experiment_id: int
    author: str
    entry_date: datetime
    content_markdown: str
    created_at: datetime


class NotebookEntryCreate(BaseModel):
    author: str = ""
    content_markdown: str = ""


class AssayResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    experiment_id: int
    assay_type: str
    summary: str
    data: dict = {}
    file_ref: str
    recorded_at: datetime


class AssayResultCreate(BaseModel):
    assay_type: str = "other"
    summary: str = ""
    data: dict = {}
    file_ref: str = ""


class NextExperimentSuggestion(BaseModel):
    hypothesis_number: int
    hypothesis_title: str
    step: HypothesisStepOut
    reason: str


# --- Layer 6: Executive Dashboard ---
class ProjectHealthOut(BaseModel):
    candidate_slug: str
    candidate_name: str
    checklist_completion_pct: float
    avg_hypothesis_confidence: float
    open_high_risk_flags: int
    experiments_in_progress: int
    experiments_completed: int
    milestones_total: int
    scoring_composite: float
