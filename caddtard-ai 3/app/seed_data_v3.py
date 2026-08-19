"""
v3.0 seed data: CMC/nonclinical/regulatory readiness requirements for the two
real repurposing candidates identified in the chromoblastomycosis pathway
deep dive (tricyclazole, auranofin), plus a single clearly-marked demo study
used only to prove the CRO/vendor -> sample -> assay acceptance -> cost ->
go/no-go pipeline is wired together end to end.

Every readiness row below reflects the actual state of research as of this
build - most are "missing" because this work genuinely has not been done.
Where a row is "present" or "provisional" it cites the real reason (e.g.
auranofin's existing FDA-approved Ridaura label, confirmed live via openFDA
in this same release). tropical_disease_prv_eligibility is marked "failed"
for both candidates because chromoblastomycosis is confirmed NOT on FDA's
section-524 qualifying disease list (Second-Stage Diligence report, Aug
2026) - the platform reports that as a failed check, not a missing one.
"""

READINESS_REQUIREMENTS = [
    # --- tricyclazole-cbm: agricultural fungicide, no human pharma history ---
    {"candidate_slug": "tricyclazole-cbm", "category": "cmc", "requirement_key": "drug_substance_spec",
     "requirement_name": "Drug substance specification", "evidence_status": "missing",
     "evidence_note": "Only an agricultural-grade EPA specification exists; no pharmaceutical-grade drug substance spec has been drafted.",
     "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "cmc", "requirement_key": "drug_product_spec",
     "requirement_name": "Drug product specification", "evidence_status": "missing", "evidence_note": "No drug product (dosage form) exists.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "cmc", "requirement_key": "analytical_method_validation",
     "requirement_name": "Analytical method validation", "evidence_status": "missing", "evidence_note": "", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "cmc", "requirement_key": "stability_data",
     "requirement_name": "Stability data", "evidence_status": "missing", "evidence_note": "Agricultural formulation stability data exists but is not pharma-relevant.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "cmc", "requirement_key": "impurity_profile",
     "requirement_name": "Impurity profile", "evidence_status": "provisional",
     "evidence_note": "EPA pesticide registration includes an impurity profile, not generated to pharmaceutical ICH Q3A/B standards.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "cmc", "requirement_key": "manufacturing_vendor_qualified",
     "requirement_name": "Manufacturing vendor qualified", "evidence_status": "missing", "evidence_note": "No pharma-grade API manufacturer identified yet.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "nonclinical", "requirement_key": "glp_tox_package",
     "requirement_name": "GLP repeat-dose toxicology package", "evidence_status": "provisional",
     "evidence_note": "EPA ecotoxicology/mammalian toxicity studies exist from pesticide registration; not a GLP human-oral-dosing package.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "nonclinical", "requirement_key": "safety_pharmacology",
     "requirement_name": "Safety pharmacology", "evidence_status": "missing", "evidence_note": "", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "nonclinical", "requirement_key": "noael_exposure_margin",
     "requirement_name": "NOAEL / exposure margin", "evidence_status": "missing", "evidence_note": "", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "nonclinical", "requirement_key": "genotoxicity_package",
     "requirement_name": "Genotoxicity package", "evidence_status": "provisional", "evidence_note": "Genotoxicity studies are part of standard EPA pesticide registration data.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "nonclinical", "requirement_key": "existing_human_safety_data",
     "requirement_name": "Existing human safety data", "evidence_status": "missing", "evidence_note": "No known history of intentional human dosing.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "regulatory", "requirement_key": "regulatory_precedent",
     "requirement_name": "Existing approved-drug regulatory precedent", "evidence_status": "missing",
     "evidence_note": "No FDA drug approval for tricyclazole in any indication; openFDA label search in this release returned no match.", "evidence_source_ref": "https://api.fda.gov/drug/label.json"},
    {"candidate_slug": "tricyclazole-cbm", "category": "regulatory", "requirement_key": "fda_guidance_review",
     "requirement_name": "FDA guidance applicability review", "evidence_status": "missing", "evidence_note": "", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "regulatory", "requirement_key": "ind_pre_ind_meeting",
     "requirement_name": "Pre-IND meeting", "evidence_status": "missing", "evidence_note": "Not yet requested.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "regulatory", "requirement_key": "orphan_drug_designation_status",
     "requirement_name": "Orphan drug designation", "evidence_status": "missing", "evidence_note": "Not yet filed.", "evidence_source_ref": ""},
    {"candidate_slug": "tricyclazole-cbm", "category": "regulatory", "requirement_key": "tropical_disease_prv_eligibility",
     "requirement_name": "FDA Tropical Disease PRV eligibility", "evidence_status": "failed",
     "evidence_note": "Chromoblastomycosis is confirmed NOT on FDA's section 524 qualifying disease list (Second-Stage Diligence report, Aug 2026).", "evidence_source_ref": ""},

    # --- auranofin-cbm: FDA-approved (Ridaura, rheumatoid arthritis) ---
    {"candidate_slug": "auranofin-cbm", "category": "cmc", "requirement_key": "drug_substance_spec",
     "requirement_name": "Drug substance specification", "evidence_status": "present",
     "evidence_note": "Established USP/NDA specification exists for the approved product (Ridaura).", "evidence_source_ref": "https://dailymed.nlm.nih.gov"},
    {"candidate_slug": "auranofin-cbm", "category": "cmc", "requirement_key": "drug_product_spec",
     "requirement_name": "Drug product specification", "evidence_status": "present", "evidence_note": "Approved capsule formulation on file with FDA.", "evidence_source_ref": "https://dailymed.nlm.nih.gov"},
    {"candidate_slug": "auranofin-cbm", "category": "cmc", "requirement_key": "analytical_method_validation",
     "requirement_name": "Analytical method validation", "evidence_status": "present", "evidence_note": "Validated methods exist for the approved product.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "cmc", "requirement_key": "stability_data",
     "requirement_name": "Stability data", "evidence_status": "present", "evidence_note": "On file with FDA for the approved product; not independently re-verified by CADDTARD.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "cmc", "requirement_key": "impurity_profile",
     "requirement_name": "Impurity profile", "evidence_status": "present", "evidence_note": "Part of the original NDA.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "cmc", "requirement_key": "manufacturing_vendor_qualified",
     "requirement_name": "Manufacturing vendor qualified", "evidence_status": "provisional",
     "evidence_note": "An approved-product manufacturer exists; no supply agreement is in place for an NTD-indication development program.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "nonclinical", "requirement_key": "glp_tox_package",
     "requirement_name": "GLP repeat-dose toxicology package", "evidence_status": "provisional",
     "evidence_note": "Extensive rheumatoid-arthritis-indication human safety data exists; no disease-specific (dose/duration) GLP tox package for chromoblastomycosis exists yet.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "nonclinical", "requirement_key": "safety_pharmacology",
     "requirement_name": "Safety pharmacology", "evidence_status": "provisional", "evidence_note": "Established for the approved indication; not population-specific to NTD-endemic settings.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "nonclinical", "requirement_key": "noael_exposure_margin",
     "requirement_name": "NOAEL / exposure margin", "evidence_status": "missing", "evidence_note": "Not yet established for the antifungal dosing regimen under consideration.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "nonclinical", "requirement_key": "genotoxicity_package",
     "requirement_name": "Genotoxicity package", "evidence_status": "present", "evidence_note": "Part of the original approval package.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "nonclinical", "requirement_key": "existing_human_safety_data",
     "requirement_name": "Existing human safety data", "evidence_status": "present", "evidence_note": "Decades of rheumatoid arthritis clinical use.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "regulatory", "requirement_key": "regulatory_precedent",
     "requirement_name": "Existing approved-drug regulatory precedent", "evidence_status": "present",
     "evidence_note": "FDA-approved as Ridaura; confirmed live via openFDA label search in this release.", "evidence_source_ref": "https://api.fda.gov/drug/label.json"},
    {"candidate_slug": "auranofin-cbm", "category": "regulatory", "requirement_key": "fda_guidance_review",
     "requirement_name": "FDA guidance applicability review", "evidence_status": "missing", "evidence_note": "No disease-specific FDA guidance exists for chromoblastomycosis.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "regulatory", "requirement_key": "ind_pre_ind_meeting",
     "requirement_name": "Pre-IND meeting", "evidence_status": "missing", "evidence_note": "Not yet requested.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "regulatory", "requirement_key": "orphan_drug_designation_status",
     "requirement_name": "Orphan drug designation", "evidence_status": "missing", "evidence_note": "Not yet filed for this indication.", "evidence_source_ref": ""},
    {"candidate_slug": "auranofin-cbm", "category": "regulatory", "requirement_key": "tropical_disease_prv_eligibility",
     "requirement_name": "FDA Tropical Disease PRV eligibility", "evidence_status": "failed",
     "evidence_note": "Chromoblastomycosis is confirmed NOT on FDA's section 524 qualifying disease list (Second-Stage Diligence report, Aug 2026).", "evidence_source_ref": ""},
]


# One demo study, imported through the exact same CSV import functions the
# API exposes, to prove the pipeline is wired end to end. Every row is
# fictional and clearly labeled - is_demo=True on the Study row, and every
# imported_from field says DEMO_SEED so nobody mistakes this for a real vendor.
DEMO_VENDOR_CSV = """name,country,capability_tags,quality_systems,website,contact_email,verified_source
DEMO VENDOR - not real,United States,"in_vivo,murine_model,GLP_tox",GLP,https://example.com,demo@example.com,DEMO_SEED - fictional row proving the import pipeline only
"""

DEMO_QUOTE_CSV = """vendor_name,study_type,scope_description,price_usd,turnaround_days,quote_date,quote_document_ref
DEMO VENDOR - not real,murine efficacy model,DEMO scope - fictional,84500,90,2026-02-01,DEMO_SEED
"""

DEMO_SAMPLE_CSV = """sample_id_external,sample_type,current_location,current_custodian,status
DEMO-0001,tissue biopsy,DEMO freezer,DEMO custodian,collected
"""

DEMO_ASSAY_CSV = """assay_name,metric_name,comparator,threshold_low,threshold_high,unit,measured_value
fungal burden reduction,CFU_log_reduction,gte,1.0,,log10 CFU/g tissue,1.4
"""

DEMO_COST_CSV = """category,budgeted_usd,actual_usd
vendor_quote,84500,84500
"""
