"""
Single source of truth mapping an agent's DB key (AgentDefinition.key) to its
callable run() function. v3.0 adds eight real-live-data agents (Europe PMC,
openFDA x2, NIH RePORTER, WHO GHO, Reactome, PubChem, PatentsView) to the 12
already implemented in v2.0, taking the platform from 12 to 20 agents that
genuinely call an external live data source on every scheduled run - not a
larger number of stub/planned rows. interval_minutes now lives on each
AgentDefinition row (seeded from app/seed_data_v2.py), so adding agent #21
doesn't require a new env var or a change to this file's shape.
"""
from app.agents import (
    ai_science_agents,
    burden_agent,
    compound_agent,
    development_agents,
    disease_biology_agents,
    funding_agents,
    genomics_agent,
    genomics_ext_agents,
    literature_agent,
    literature_ext_agent,
    ontology_agent,
    pathway_ext_agent,
    patent_agent,
    regulatory_agents,
    structural_agent,
    therapeutics_agents,
)

AGENT_FUNCTIONS = {
    genomics_agent.NAME: genomics_agent.run,
    literature_agent.NAME: literature_agent.run,
    structural_agent.NAME: structural_agent.run,
    ontology_agent.NAME: ontology_agent.run,
    genomics_ext_agents.ENSEMBL_NAME: genomics_ext_agents.run_gene_transcript,
    genomics_ext_agents.GNOMAD_NAME: genomics_ext_agents.run_population_genetics,
    disease_biology_agents.NAME: disease_biology_agents.run,
    therapeutics_agents.NAME: therapeutics_agents.run,
    ai_science_agents.NAME: ai_science_agents.run,
    development_agents.CLINICAL_NAME: development_agents.run_clinical,
    development_agents.COMPETITIVE_NAME: development_agents.run_competitive_intelligence,
    development_agents.GITHUB_NAME: development_agents.run_github_watch,
    # --- v3.0 real-live-data agents ---
    literature_ext_agent.NAME: literature_ext_agent.run,
    regulatory_agents.REGULATORY_NAME: regulatory_agents.run_regulatory_precedent,
    regulatory_agents.CMC_LABEL_NAME: regulatory_agents.run_cmc_product_label,
    funding_agents.NAME: funding_agents.run,
    burden_agent.NAME: burden_agent.run,
    pathway_ext_agent.NAME: pathway_ext_agent.run,
    compound_agent.NAME: compound_agent.run,
    patent_agent.NAME: patent_agent.run,
}
