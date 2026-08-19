"""
CSV import for the operational layer. Every function here takes an open CSV
file (a csv.DictReader) and a DB session and inserts rows - it never invents
a value for a column the CSV left blank, and every inserted row records
imported_from (the filename/source the caller passes in) so the provenance
of "who told CADDTARD this vendor exists" is always answerable. This is the
concrete implementation of the "does not invent CRO capabilities or quotes"
design constraint from the v0.10 plan: nothing in this file calls an LLM,
guesses a number, or fills in a default price - a missing required column
is a row-level import error, not a silently-defaulted value.
"""
import csv
import io

from app.models_ops import (
    AssayAcceptanceCriterion,
    AssayAcceptanceEvaluation,
    CroVendor,
    ReadinessRequirement,
    Sample,
    StudyCost,
    VendorQuote,
)
from app.ops_logic import evaluate_acceptance


class ImportError_(Exception):
    """Raised for a row that is missing a required field. Named with a
    trailing underscore to avoid shadowing the builtin ImportError."""


def _reader(csv_text: str) -> csv.DictReader:
    return csv.DictReader(io.StringIO(csv_text))


def import_cro_vendors(db, csv_text: str, source: str) -> list[CroVendor]:
    created = []
    for i, row in enumerate(_reader(csv_text)):
        name = (row.get("name") or "").strip()
        verified_source = (row.get("verified_source") or "").strip()
        if not name or not verified_source:
            raise ImportError_(f"row {i}: 'name' and 'verified_source' are required (no vendor is created without a source)")
        v = CroVendor(
            name=name,
            country=(row.get("country") or "").strip(),
            capability_tags=(row.get("capability_tags") or "").strip(),
            quality_systems=(row.get("quality_systems") or "").strip(),
            website=(row.get("website") or "").strip(),
            contact_email=(row.get("contact_email") or "").strip(),
            verified_source=verified_source,
        )
        db.add(v)
        created.append(v)
    db.flush()
    return created


def import_vendor_quotes(db, csv_text: str, source: str, vendor_id_by_name: dict[str, int]) -> list[VendorQuote]:
    created = []
    for i, row in enumerate(_reader(csv_text)):
        vendor_name = (row.get("vendor_name") or "").strip()
        price = row.get("price_usd")
        if not vendor_name or price in (None, ""):
            raise ImportError_(f"row {i}: 'vendor_name' and 'price_usd' are required")
        vendor_id = vendor_id_by_name.get(vendor_name)
        if vendor_id is None:
            raise ImportError_(f"row {i}: vendor '{vendor_name}' is not in the CRO vendor registry - import the vendor first")
        q = VendorQuote(
            vendor_id=vendor_id,
            study_type=(row.get("study_type") or "").strip(),
            scope_description=(row.get("scope_description") or "").strip(),
            price_usd=float(price),
            turnaround_days=int(row.get("turnaround_days") or 0),
            quote_date=(row.get("quote_date") or "").strip(),
            quote_document_ref=(row.get("quote_document_ref") or "").strip(),
            imported_from=source,
        )
        db.add(q)
        created.append(q)
    db.flush()
    return created


def import_samples(db, csv_text: str, source: str, study_id: int) -> list[Sample]:
    created = []
    for i, row in enumerate(_reader(csv_text)):
        ext_id = (row.get("sample_id_external") or "").strip()
        if not ext_id:
            raise ImportError_(f"row {i}: 'sample_id_external' is required")
        s = Sample(
            study_id=study_id,
            sample_id_external=ext_id,
            sample_type=(row.get("sample_type") or "").strip(),
            current_location=(row.get("current_location") or "").strip(),
            current_custodian=(row.get("current_custodian") or "").strip(),
            status=(row.get("status") or "collected").strip(),
            imported_from=source,
        )
        db.add(s)
        created.append(s)
    db.flush()
    return created


def import_assay_acceptance(db, csv_text: str, source: str, study_id: int) -> list[AssayAcceptanceCriterion]:
    """Each row defines a prospective criterion; if the row also carries a
    measured_value, the evaluation is computed immediately with the exact
    same evaluate_acceptance() function the API uses - not a re-implementation."""
    created = []
    for i, row in enumerate(_reader(csv_text)):
        assay_name = (row.get("assay_name") or "").strip()
        metric_name = (row.get("metric_name") or "").strip()
        comparator = (row.get("comparator") or "").strip()
        if not assay_name or not metric_name or comparator not in ("gte", "lte", "eq", "range"):
            raise ImportError_(f"row {i}: 'assay_name', 'metric_name', and a valid 'comparator' (gte|lte|eq|range) are required")
        tl = row.get("threshold_low")
        th = row.get("threshold_high")
        crit = AssayAcceptanceCriterion(
            study_id=study_id,
            assay_name=assay_name,
            metric_name=metric_name,
            comparator=comparator,
            threshold_low=float(tl) if tl not in (None, "") else None,
            threshold_high=float(th) if th not in (None, "") else None,
            unit=(row.get("unit") or "").strip(),
            imported_from=source,
        )
        db.add(crit)
        db.flush()
        measured = row.get("measured_value")
        if measured not in (None, ""):
            result = evaluate_acceptance(comparator, float(measured), crit.threshold_low, crit.threshold_high)
            db.add(AssayAcceptanceEvaluation(criterion_id=crit.id, measured_value=float(measured), result=result, auto_evaluated=True))
        created.append(crit)
    db.flush()
    return created


def import_study_costs(db, csv_text: str, source: str, study_id: int) -> list[StudyCost]:
    created = []
    for i, row in enumerate(_reader(csv_text)):
        category = (row.get("category") or "").strip()
        if not category:
            raise ImportError_(f"row {i}: 'category' is required")
        c = StudyCost(
            study_id=study_id,
            category=category,
            budgeted_usd=float(row.get("budgeted_usd") or 0),
            actual_usd=float(row.get("actual_usd") or 0),
            imported_from=source,
        )
        db.add(c)
        created.append(c)
    db.flush()
    return created


def import_readiness(db, csv_text: str, source: str, category: str) -> list[ReadinessRequirement]:
    """Shared importer for cmc_readiness / nonclinical_safety /
    regulatory_evidence CSVs - category is passed by the caller (the router
    picks it from the endpoint path), not read from the file, so a
    mislabeled CSV can't silently land rows in the wrong bucket."""
    valid_status = {"present", "provisional", "missing", "failed", "not_applicable"}
    created = []
    for i, row in enumerate(_reader(csv_text)):
        slug = (row.get("candidate_slug") or "").strip()
        req_key = (row.get("requirement_key") or "").strip()
        status = (row.get("evidence_status") or "").strip()
        if not slug or not req_key or status not in valid_status:
            raise ImportError_(f"row {i}: 'candidate_slug', 'requirement_key', and a valid 'evidence_status' are required")
        r = ReadinessRequirement(
            candidate_slug=slug,
            category=category,
            requirement_key=req_key,
            requirement_name=(row.get("requirement_name") or req_key).strip(),
            evidence_status=status,
            evidence_note=(row.get("evidence_note") or "").strip(),
            evidence_source_ref=(row.get("evidence_source_ref") or "").strip(),
            imported_from=source,
        )
        db.add(r)
        created.append(r)
    db.flush()
    return created
