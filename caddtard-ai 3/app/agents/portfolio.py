"""
Shared disease/compound term lists reused across the newer cross-portfolio
agents (v3.0). The original v1/v2 agents were scoped tightly to the three
V-ATPase genes; CADDTARD OS's second commercial vertical (neglected tropical
diseases - chromoblastomycosis, eumycetoma, loiasis, Buruli ulcer) has no
gene-table equivalent yet, so agents that need a disease-area term list pull
from here instead of re-declaring it. Kept intentionally small and named,
not auto-generated, so every term is one a human chose and can audit.
"""

RARE_DISEASE_TERMS = [
    "distal renal tubular acidosis",
    "ATP6V0C developmental epileptic encephalopathy",
    "TCIRG1 osteopetrosis",
]

NTD_TERMS = [
    "chromoblastomycosis",
    "eumycetoma",
    "loiasis",
]

ALL_DISEASE_TERMS = RARE_DISEASE_TERMS + NTD_TERMS

# Repurposing/chemical-matter candidates identified in the Aug 2026 diligence
# work (chromoblastomycosis pathway deep dive) plus the existing V-ATPase
# pharmacology terms, for agents that query per-compound.
COMPOUND_TERMS = [
    "tricyclazole",
    "auranofin",
    "itraconazole",
    "fosravuconazole",
    "bafilomycin A1",
]
