"""
v3.0 Operational Layer: CRO/vendor management, protocol execution, sample
chain-of-custody, assay acceptance, study cost tracking, and go/no-go
governance - plus a generalized CMC/nonclinical/regulatory readiness ledger.

Design principle carried over from the CADDTARD OS v0.10/v0.11 plan and kept
here: this layer never invents vendor capabilities, quotes, cost figures, or
readiness evidence. Every row in CroVendor, VendorQuote, Sample, StudyCost,
and ReadinessRequirement is either created through the CSV import endpoints
(see app/ops_import.py and import_templates/*.csv) or entered by a human
through the API - no agent scores or synthesizes this data out of thin air.
Only the *evaluation* logic (assay acceptance pass/fail, cost variance,
go/no-go recommendation) is computed, and it is computed in app/ops_logic.py
from data that is already on file, never invented at evaluation time either.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# CRO / Vendor registry
# ---------------------------------------------------------------------------
class CroVendor(Base):
    __tablename__ = "cro_vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    country: Mapped[str] = mapped_column(String(128), default="")
    capability_tags: Mapped[str] = mapped_column(String(512), default="")  # comma-separated, e.g. "in_vivo,GLP_tox,murine_model"
    quality_systems: Mapped[str] = mapped_column(String(256), default="")  # comma-separated, e.g. "GLP,ISO17025"
    website: Mapped[str] = mapped_column(String(512), default="")
    contact_email: Mapped[str] = mapped_column(String(256), default="")
    verified_source: Mapped[str] = mapped_column(String(512), default="")  # where this vendor record came from - required, never blank on import
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    quotes: Mapped[list["VendorQuote"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")


class VendorQuote(Base):
    __tablename__ = "vendor_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("cro_vendors.id"))
    study_type: Mapped[str] = mapped_column(String(128), default="")  # e.g. "murine efficacy model"
    scope_description: Mapped[str] = mapped_column(Text, default="")
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    turnaround_days: Mapped[int] = mapped_column(Integer, default=0)
    quote_date: Mapped[str] = mapped_column(String(16), default="")  # ISO date string as filed
    quote_document_ref: Mapped[str] = mapped_column(String(512), default="")  # file/reference the quote came from
    imported_from: Mapped[str] = mapped_column(String(256), default="")
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    vendor: Mapped["CroVendor"] = relationship(back_populates="quotes")


# ---------------------------------------------------------------------------
# Protocol execution (extends the existing Protocol model in app/models.py
# with per-step execution tracking; protocol *versioning* already exists via
# Protocol.version, one row per version)
# ---------------------------------------------------------------------------
class ProtocolExecutionStep(Base):
    __tablename__ = "protocol_execution_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocol_id: Mapped[int] = mapped_column(ForeignKey("protocols.id"))
    step_number: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="pending")  # pending|in_progress|complete|deviation
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


# ---------------------------------------------------------------------------
# Operational study registry (a CRO-executed study; distinct from the
# internal Experiment model, which tracks in-house bench work)
# ---------------------------------------------------------------------------
class Study(Base):
    __tablename__ = "studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    candidate_slug: Mapped[str] = mapped_column(String(32), default="")
    study_type: Mapped[str] = mapped_column(String(128), default="")
    cro_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("cro_vendors.id"), nullable=True)
    owner: Mapped[str] = mapped_column(String(128), default="")
    target_start_date: Mapped[str] = mapped_column(String(16), default="")
    target_end_date: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(24), default="planned")  # planned|active|completed|cancelled
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)  # True only for the seeded example study - never set by import
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    milestones: Mapped[list["StudyMilestone"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    samples: Mapped[list["Sample"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    acceptance_criteria: Mapped[list["AssayAcceptanceCriterion"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    costs: Mapped[list["StudyCost"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    go_no_go_decisions: Mapped[list["GoNoGoDecision"]] = relationship(back_populates="study", cascade="all, delete-orphan")


class StudyMilestone(Base):
    __tablename__ = "study_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"))
    name: Mapped[str] = mapped_column(String(256))
    target_date: Mapped[str] = mapped_column(String(16), default="")
    actual_date: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(24), default="on_track")  # on_track|at_risk|late|complete
    risk_note: Mapped[str] = mapped_column(Text, default="")

    study: Mapped["Study"] = relationship(back_populates="milestones")


# ---------------------------------------------------------------------------
# Sample inventory + chain of custody
# ---------------------------------------------------------------------------
class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"))
    sample_id_external: Mapped[str] = mapped_column(String(128), default="")  # the CRO's or lab's own ID for this sample
    sample_type: Mapped[str] = mapped_column(String(128), default="")
    current_location: Mapped[str] = mapped_column(String(256), default="")
    current_custodian: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(24), default="collected")  # collected|in_transit|received|analyzed|disposed
    imported_from: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    study: Mapped["Study"] = relationship(back_populates="samples")
    custody_events: Mapped[list["ChainOfCustodyEvent"]] = relationship(back_populates="sample", cascade="all, delete-orphan")


class ChainOfCustodyEvent(Base):
    __tablename__ = "chain_of_custody_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"))
    event_type: Mapped[str] = mapped_column(String(24), default="")  # collected|transferred|received|analyzed|disposed
    from_custodian: Mapped[str] = mapped_column(String(128), default="")
    to_custodian: Mapped[str] = mapped_column(String(128), default="")
    location: Mapped[str] = mapped_column(String(256), default="")
    event_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notes: Mapped[str] = mapped_column(Text, default="")

    sample: Mapped["Sample"] = relationship(back_populates="custody_events")


# ---------------------------------------------------------------------------
# Prospective assay acceptance criteria + automatic evaluation against
# measured results. "Prospective" means the criterion must exist (imported or
# entered) before a measured_value is evaluated against it - the evaluation
# function in app/ops_logic.py refuses to grade a result against a criterion
# created after the measurement, which is the whole point of "prospective".
# ---------------------------------------------------------------------------
class AssayAcceptanceCriterion(Base):
    __tablename__ = "assay_acceptance_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"))
    assay_name: Mapped[str] = mapped_column(String(128), default="")
    metric_name: Mapped[str] = mapped_column(String(128), default="")
    comparator: Mapped[str] = mapped_column(String(8), default="gte")  # gte|lte|eq|range
    threshold_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="")
    imported_from: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    study: Mapped["Study"] = relationship(back_populates="acceptance_criteria")
    evaluations: Mapped[list["AssayAcceptanceEvaluation"]] = relationship(back_populates="criterion", cascade="all, delete-orphan")


class AssayAcceptanceEvaluation(Base):
    __tablename__ = "assay_acceptance_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("assay_acceptance_criteria.id"))
    measured_value: Mapped[float] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(16), default="not_evaluated")  # pass|fail|not_evaluated
    auto_evaluated: Mapped[bool] = mapped_column(Boolean, default=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    criterion: Mapped["AssayAcceptanceCriterion"] = relationship(back_populates="evaluations")


# ---------------------------------------------------------------------------
# Study cost tracking
# ---------------------------------------------------------------------------
class StudyCost(Base):
    __tablename__ = "study_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"))
    category: Mapped[str] = mapped_column(String(64), default="")  # vendor_quote|internal|reagents|travel|other
    budgeted_usd: Mapped[float] = mapped_column(Float, default=0.0)
    actual_usd: Mapped[float] = mapped_column(Float, default=0.0)
    imported_from: Mapped[str] = mapped_column(String(256), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    study: Mapped["Study"] = relationship(back_populates="costs")


# ---------------------------------------------------------------------------
# Go/No-Go governance. system_* fields are computed by
# app/ops_logic.compute_go_no_go and are always prefixed "system_" so the
# schema itself makes clear these are proposals, not decisions. A human
# decision is a separate, required step.
# ---------------------------------------------------------------------------
class GoNoGoDecision(Base):
    __tablename__ = "go_no_go_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"))
    system_recommendation: Mapped[str] = mapped_column(String(16), default="insufficient_data")  # go|no_go|hold|insufficient_data
    system_rationale: Mapped[str] = mapped_column(Text, default="")
    system_measured_candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    system_assay_acceptance_pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    system_budget_status: Mapped[str] = mapped_column(String(16), default="unknown")  # on_budget|over|under|unknown
    system_timeline_status: Mapped[str] = mapped_column(String(16), default="unknown")  # on_track|at_risk|late|unknown
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    human_decision: Mapped[str] = mapped_column(String(16), default="pending")  # approved|rejected|deferred|pending
    human_reviewer: Mapped[str] = mapped_column(String(128), default="")
    human_decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    human_notes: Mapped[str] = mapped_column(Text, default="")

    study: Mapped["Study"] = relationship(back_populates="go_no_go_decisions")


# ---------------------------------------------------------------------------
# CMC / Nonclinical Safety / Regulatory readiness ledger. One generic table
# (category discriminates) rather than one table per document type - every
# requirement carries an explicit evidence_status so a missing package cannot
# be silently rendered as a confident-looking score. Default status on seed
# is "missing" for every real CADDTARD candidate, because none of this work
# exists yet - the platform starts conservative by design, not by omission.
# ---------------------------------------------------------------------------
class ReadinessRequirement(Base):
    __tablename__ = "readiness_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_slug: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(24))  # cmc|nonclinical|regulatory|ind_cta
    requirement_key: Mapped[str] = mapped_column(String(64))
    requirement_name: Mapped[str] = mapped_column(String(256))
    evidence_status: Mapped[str] = mapped_column(String(16), default="missing")  # present|provisional|missing|failed|not_applicable
    evidence_note: Mapped[str] = mapped_column(Text, default="")
    evidence_source_ref: Mapped[str] = mapped_column(String(512), default="")
    imported_from: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
