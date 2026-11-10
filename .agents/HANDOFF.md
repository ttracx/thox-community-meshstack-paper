# Agent Handoff — thox-community-meshstack-paper

## Status
- DONE: v1.0.0 paper pack built and verified (13-page PDF/HTML/DOCX + demo); Virtual Lab implemented with 5/5 tests passing; repository created PUBLIC on Tommy's direct order (2026-11-10); formal release v1.0.0 with PDF, HTML and demo attached.
- IN PROGRESS: none inside this repo.
- NEXT (founder-gated, do not self-start): founder consent to exact bytes, Zenodo deposit, one-pass association (HF whitepapers, website page, Model Factory), LinkedIn post (founders' call).

## Key files
- `exp/results/summary.json` — single evidence source; every paper number traces here.
- `exp/community_lab.py` — lab implementation (planner, grant DAG, ledger).
- `wp/build_paper.py` — paper builder; reads summary.json only.
- `dist/` — shipped editions; never hand-edit.

## Conventions
- Evidence classes on every number; no device claims from lab runs.
- Rebuild order: lab -> summary.json -> figures -> paper HTML -> PDF (WeasyPrint) -> DOCX (LibreOffice).
- Byte changes after release = new edition + new release.

## Blockers and open questions
- No DOI yet; CITATION.cff states this explicitly.
- Space (Muse artifact `thox-community-meshstack-virtual-lab`) is owned by the parent lane, not this repo.

## Exact-edition hashes (SHA-256, v1.0.0)
- Paper PDF: 7988d0b48ec441e6d594a0dc3a541e44b96ae4ff3199f91cdf193be5c3a00055
- Paper HTML: 57dac701c57aac7ada826f855d592c211a36c65cefcf383b8c3c8fd8952a8c6a
- Demo HTML: 3634f61651e808613afcd6d86120e0b65a3072531a71a80dccdfbcd0fda65555
- summary.json: a9101d04957d30227b46f37f2e7f19bb7930030cd8d236f83d6c3e0e96d50b48

Last verified: 2026-11-10 by Sadie Weaving (CAO lane, GitHub route: KnightHub gh as ttracx).
