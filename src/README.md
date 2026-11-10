# THOX Community MeshStack — Lab Handoff

**Purpose:** Stand up a Virtual Lab that generates supporting evidence for the research specification  
**THOX MeshStack Community Mesh: Opt-In User-Contributed Hardware for a Privacy-Centric Shared Computing and Capacity-Priced Distributed Inference Mesh**

**Authors (human principals):** Craig Ross, Tommy Xaypanya  
**Status:** Research specification only. No production community mesh is claimed.  
**Date:** 2026-11-10

## Handoff Contents

| File | Purpose |
|------|---------|
| `lab_admission.py` | Two-domain fail-closed admission and capacity calculator |
| `lab_evidence.py` | Generates CALCULATED capacity tables and SIMULATED placement runs |
| `tikz_diagrams.tex` | Full TikZ source for the three figures (with captions) |
| `THOX_Community_MeshStack_Paper.md` | Research specification |
| `capacity_table.md` | Pre-computed capacity table |
| `figures/` | PNG previews of the diagrams |

## Evidence Protocol

All evidence must be labeled:

- **MEASURED** — only numbers taken from the household paper (Ross & Xaypanya, 2026, DOI 10.5281/zenodo.23969070) on stated host classes.
- **CALCULATED** — results of the two-domain admission arithmetic in this lab.
- **SIMULATED** — multi-node placement runs under stated churn and capacity assumptions.

No device measurements and no community-mesh measurements are claimed.

## How to Generate Evidence

```bash
python3 lab_evidence.py
```

This writes:
- `evidence/capacity_table.csv`
- `evidence/capacity_table.md`
- `evidence/placement_runs.json`

## Next Actions

1. Run `lab_evidence.py` and attach the generated tables to the paper.
2. Extend the lab with a grant-DAG simulator (principal-bound, attenuable, live verification, crypto-shred).
3. Add a simple multi-node pipeline stage scheduler that consumes the admission results.
4. Package for Zenodo with the TikZ sources and this lab.
5. Index on Hugging Face Papers under Thox-ai after a DOI is assigned.

## Privacy Invariants (must be preserved in any lab implementation)

- Coordinator receives only metadata.
- Payload paths are authenticated and grant-gated.
- KV and secrets are principal-bound; no cross-principal reuse.
- Admission fails closed.
- Whole-request routing is preferred when a single node can place the model.

[sadie-node:sadie-grok]
