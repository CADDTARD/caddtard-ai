"""Verified proof-of-concept design for the ATP6V0A1 program.

The content in this module is intentionally separated from experimental
results.  It defines the decision framework, assay expectations and evidence
boundaries for the program; it does not claim that any gate has passed.
"""

PROGRAM = {
    "title": "ATP6V0A1 Leu756Arg proof of concept",
    "gene": "ATP6V0A1",
    "transcript": "NM_001130020.1",
    "program_variant": "c.2267T>G; p.(Leu756Arg)",
    "mission": (
        "Test whether restoring functional ATP6V0A1 can repair lysosomal biology "
        "and improve neuronal function without creating an overexpression or toxicity liability."
    ),
    "plain_language": (
        "The cell's recycling system needs an acid-powered pump. This study asks whether repairing "
        "one pump component restores recycling and helps neurons communicate normally."
    ),
}

EVIDENCE_BOUNDARY = {
    "variant_status": "Program-supplied identity; variant-specific pathogenic mechanism not independently established",
    "model_anchor": (
        "ATP6V0A1 A512P models support the lysosome-autophagy-mTOR-synapse pathway as a biologically "
        "plausible anchor, not as proof that Leu756Arg behaves identically."
    ),
    "decision_rule": (
        "Treat Leu756Arg mechanism, rescue magnitude and dose window as hypotheses until confirmed in "
        "isogenic and patient-relevant models."
    ),
}

BIOLOGY_CHAIN = [
    {
        "step": 1,
        "label": "Build the pump",
        "plain": "Check whether the ATP6V0A1 pump component is present and reaches the right cellular compartment.",
        "scientist": "Quantify ATP6V0A1 abundance, lysosomal localization and V0-V1 complex association.",
        "assays": ["Immunoblot", "Immunofluorescence colocalization", "Complex association assay"],
    },
    {
        "step": 2,
        "label": "Power the pump",
        "plain": "Measure whether the repaired pump can actually move protons.",
        "scientist": "Measure V-ATPase proton-pump function and normalize activity to ATP6V0A1 protein abundance.",
        "assays": ["Organelle acidification kinetics", "Direct proton-pumping readout", "Activity-to-protein ratio"],
    },
    {
        "step": 3,
        "label": "Acidify the lysosome",
        "plain": "Confirm that the cell's recycling compartment returns to its working acidity.",
        "scientist": "Use calibrated ratiometric lysosomal pH measurement; intensity-only dyes are supportive, not definitive.",
        "assays": ["LysoSensor Yellow/Blue DND-160", "Ionophore-based pH calibration curve"],
    },
    {
        "step": 4,
        "label": "Activate the recycler",
        "plain": "Test whether acid-dependent enzymes can mature and digest material again.",
        "scientist": "Measure cathepsin D maturation, localization and enzymatic activity.",
        "assays": ["Pro/mature cathepsin D immunoblot", "Activity assay", "Lysosomal localization"],
    },
    {
        "step": 5,
        "label": "Restore cellular cleanup",
        "plain": "Track whether damaged material moves through the recycling pathway instead of piling up.",
        "scientist": "Measure autophagic flux with perturbation and tandem reporters; static LC3-II alone is insufficient.",
        "assays": ["LC3-II and p62 with flux control", "mCherry-GFP-LC3 reporter", "Autolysosome quantification"],
    },
    {
        "step": 6,
        "label": "Reset nutrient signaling",
        "plain": "See whether the cell's growth-and-energy signaling returns toward the healthy reference range.",
        "scientist": "Use pS6/S6 as the primary mTORC1 readout with p70S6K and 4E-BP1 as orthogonal measures.",
        "assays": ["pS6/S6", "p70S6K", "4E-BP1"],
    },
    {
        "step": 7,
        "label": "Protect the neuron",
        "plain": "Confirm that neurons survive and keep healthy branches without a toxicity signal.",
        "scientist": "Quantify viability, apoptosis and MAP2/TUJ1 morphology across the intended exposure window.",
        "assays": ["Viability", "Apoptosis", "MAP2/TUJ1 neurite morphology", "Dose-response toxicity"],
    },
    {
        "step": 8,
        "label": "Reconnect the network",
        "plain": "Ask whether neurons form healthier connections and communicate more normally.",
        "scientist": "Integrate synaptic puncta, patch clamp and longitudinal MEA; success is normalization, not simply more firing.",
        "assays": ["SYN1/synaptophysin and PSD95", "mEPSC/mIPSC patch clamp", "MEA network dynamics"],
    },
]

EXPERIMENTAL_GROUPS = [
    {"key": "wt", "name": "Isogenic healthy reference", "purpose": "Defines the target biological range."},
    {"key": "disease", "name": "Leu756Arg disease model", "purpose": "Tests the program variant phenotype."},
    {"key": "lof", "name": "Loss-of-function comparator", "purpose": "Separates variant-specific effects from reduced gene function."},
    {"key": "replacement", "name": "Disease plus WT replacement", "purpose": "Measures rescue by functional ATP6V0A1."},
    {"key": "lowering", "name": "Disease plus endogenous lowering", "purpose": "Tests whether reducing the mutant/endogenous species changes phenotype."},
    {"key": "silence_replace", "name": "Silence plus replacement", "purpose": "Tests whether removing the disease allele improves the replacement response."},
    {"key": "mechanistic_control", "name": "Orthogonal mechanism control", "purpose": "Shows whether a pathway-level rescue follows the proposed mechanism."},
]

DEVELOPMENT_TIERS = [
    {
        "tier": 1,
        "name": "Fast mechanism screen",
        "models": "Engineered HEK293FT and Neuro-2a",
        "decision": "Confirm expression, localization, acidification and an initial rescue window before costly neuronal work.",
    },
    {
        "tier": 2,
        "name": "Human neuron confirmation",
        "models": "Isogenic iPSC-derived neurons, with patient-derived cells when available",
        "decision": "Replicate lysosomal, flux, signaling, viability and synaptic effects in a disease-relevant human system.",
    },
    {
        "tier": 3,
        "name": "Functional depth",
        "models": "Reporter neurons, patch clamp and longitudinal MEA",
        "decision": "Demonstrate that molecular rescue produces reproducible single-cell and network normalization.",
    },
    {
        "tier": 4,
        "name": "Translational bridge",
        "models": "A512P mouse for pathway anchoring, then a Leu756Arg knock-in model if justified",
        "decision": "Establish exposure, tissue pharmacology, safety and in-vivo functional relevance without conflating variants.",
    },
]

GO_NO_GO_GATES = [
    {"id": "target", "name": "Target restoration", "question": "Is functional ATP6V0A1 restored in the correct compartment and dose window?"},
    {"id": "lysosome", "name": "Lysosome rescue", "question": "Do calibrated pH and cathepsin D activity both move toward the healthy reference?"},
    {"id": "flux", "name": "Autophagy flux", "question": "Does dynamic flux improve rather than only changing a static marker?"},
    {"id": "signaling", "name": "mTORC1 normalization", "question": "Does pS6/S6 normalize with orthogonal pathway support?"},
    {"id": "neuron", "name": "Neuronal benefit without toxicity", "question": "Do survival and morphology improve across a credible therapeutic window?"},
    {"id": "function", "name": "Functional rescue", "question": "Do patch-clamp and MEA phenotypes normalize toward isogenic controls?"},
    {"id": "replication", "name": "Cross-model replication", "question": "Does the causal chain reproduce from engineered cells to human neurons and an appropriate in-vivo model?"},
]

RIGOR_LOCKS = [
    "Pre-specify primary endpoints, acceptance ranges and exclusion criteria before unblinding.",
    "Use independent biological replicates, including independent neuronal differentiations.",
    "Randomize allocation and blind acquisition and analysis where feasible.",
    "Confirm exact variant identity, zygosity, transcript and off-target profile before phenotyping.",
    "Use calibrated ratiometric lysosomal pH and dynamic autophagy-flux methods.",
    "Separate vector exposure, ATP6V0A1 abundance and functional rescue to define an overexpression window.",
    "Normalize synaptic structure to neurite length and network activity toward isogenic reference behavior.",
    "Replicate the critical result independently before treating it as funder-grade evidence.",
]

FUNDING_MILESTONES = [
    {"name": "Experimental design locked", "status": "complete", "unlocks": "Comparable proposals, CRO quotes and a common data package."},
    {"name": "Variant mechanism established", "status": "evidence_gap", "unlocks": "A defensible causal story specific to Leu756Arg."},
    {"name": "Cellular target engagement", "status": "planned", "unlocks": "Proof that replacement reaches and powers the intended organelle."},
    {"name": "Human-neuron rescue", "status": "planned", "unlocks": "Disease-relevant efficacy and dose-window evidence."},
    {"name": "Functional network rescue", "status": "planned", "unlocks": "A translational bridge beyond biochemical markers."},
    {"name": "In-vivo translation and safety", "status": "planned", "unlocks": "Exposure, tissue pharmacology and development risk reduction."},
    {"name": "Independent replication", "status": "planned", "unlocks": "A funder-ready evidence room with reproducible decision data."},
]

EXECUTION_COPILOTS = [
    {
        "key": "variant_detective",
        "name": "Variant Detective",
        "emoji": "🧬",
        "plain": "Checks that the genetic starting point is exactly right.",
        "scientist": "Curates transcript, allele, population frequency, predicted consequence and variant-specific evidence gaps.",
        "agent_keys": ["genomics", "gene_transcript", "population_genetics"],
        "deliverable": "Variant identity and evidence dossier",
    },
    {
        "key": "evidence_cartographer",
        "name": "Evidence Cartographer",
        "emoji": "🗺️",
        "plain": "Maps what is known, what is uncertain and what experiment comes next.",
        "scientist": "Maintains the causal chain across literature and pathway sources with explicit confidence boundaries.",
        "agent_keys": ["literature", "europepmc_literature", "pathway_intelligence"],
        "deliverable": "Traceable mechanism map and evidence ledger",
    },
    {
        "key": "model_builder",
        "name": "Model Builder",
        "emoji": "🧫",
        "plain": "Chooses the simplest model that can answer each question honestly.",
        "scientist": "Connects phenotype and structural evidence to engineered cells, isogenic neurons and in-vivo model selection.",
        "agent_keys": ["disease_phenotype", "structure_prediction"],
        "deliverable": "Model qualification and cross-model bridge",
    },
    {
        "key": "assay_guardian",
        "name": "Assay Guardian",
        "emoji": "🧪",
        "plain": "Stops attractive but misleading measurements from becoming conclusions.",
        "scientist": "Checks assay fit-for-purpose, calibration, controls, normalization, replication and gate criteria.",
        "agent_keys": ["literature", "europepmc_literature"],
        "deliverable": "Assay control matrix and QC-ready data specification",
    },
    {
        "key": "translation_navigator",
        "name": "Translation Navigator",
        "emoji": "🧭",
        "plain": "Links early results to the questions regulators and developers will ask next.",
        "scientist": "Surveys trial, regulatory precedent and product-label evidence without presenting preclinical markers as qualified endpoints.",
        "agent_keys": ["clinical_trials", "regulatory_precedent", "cmc_product_label"],
        "deliverable": "Translational and regulatory evidence map",
    },
    {
        "key": "cro_scout",
        "name": "CRO and Reagent Scout",
        "emoji": "🔎",
        "plain": "Turns the plan into realistic vendors, materials, timelines and costs.",
        "scientist": "Surfaces CRO capabilities, compound comparators and due-diligence questions; procurement still requires human qualification.",
        "agent_keys": ["competitive_intelligence", "compound_properties"],
        "deliverable": "Executable sourcing and vendor diligence package",
    },
    {
        "key": "funding_radar",
        "name": "Funding Radar",
        "emoji": "📡",
        "plain": "Matches each evidence milestone to the right source of capital.",
        "scientist": "Tracks non-dilutive opportunities and disease-burden context while keeping prevalence claims source-bound.",
        "agent_keys": ["funding_opportunities", "who_burden"],
        "deliverable": "Milestone-linked funding and burden brief",
    },
    {
        "key": "evidence_room_builder",
        "name": "Evidence Room Builder",
        "emoji": "🏛️",
        "plain": "Organizes every decision, result and limitation into a funder-friendly story.",
        "scientist": "Reserved interface for ELN/LIMS/QC ingestion, lineage, independent replication and investment-diligence export.",
        "agent_keys": [],
        "deliverable": "Audit-ready data room and investment evidence package",
    },
]

VERIFICATION_SOURCES = [
    {
        "name": "ATP6V0A1 A512P disease model",
        "url": "https://pubmed.ncbi.nlm.nih.gov/33833240/",
        "supports": "Pathway anchor linking ATP6V0A1 dysfunction to lysosomal, autophagy, mTORC1 and synaptic phenotypes.",
    },
    {
        "name": "Autophagy assay guidelines",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7996087/",
        "supports": "Dynamic flux and multiple orthogonal readouts rather than static LC3 interpretation alone.",
    },
    {
        "name": "LysoSensor Yellow/Blue DND-160",
        "url": "https://www.thermofisher.com/order/catalog/product/L7545",
        "supports": "Ratiometric acidic-organelle pH measurement with calibration requirements.",
    },
    {
        "name": "NIH rigor and reproducibility guidance",
        "url": "https://grants.nih.gov/policy-and-compliance/policy-topics/reproducibility/guidance",
        "supports": "Study design, biological variables, authentication and transparent reporting.",
    },
    {
        "name": "ARRIVE 2.0",
        "url": "https://arriveguidelines.org/arrive-guidelines",
        "supports": "Randomization, blinding, sample-size and exclusion transparency for animal work.",
    },
    {
        "name": "FDA biomarker context of use",
        "url": "https://www.fda.gov/drugs/biomarker-qualification-program/context-use",
        "supports": "The restoration score is an internal development tool, not a qualified regulatory endpoint.",
    },
]

