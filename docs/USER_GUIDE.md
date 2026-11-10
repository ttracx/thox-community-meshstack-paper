# User Guide — THOX Community MeshStack Paper

## What this is

The official THOX.ai Research paper specifying the Community Mesh extension of MeshStack, plus the complete Virtual Lab that generates its supporting evidence. It is for MeshStack subscribers, contributors and engineers who want to understand how opt-in contributed hardware can be pooled for distributed inference without giving up the household mesh's privacy properties.

**Status: preprint, not peer reviewed. No DOI has been issued yet. No production community mesh is claimed anywhere in this repository.**

## The paper in one page

- **Problem.** A household mesh is bounded by its own devices: at the published 2/4/6 GB class floors, a 27B-class model is unplaceable on a ThoxAir + ThoxMini + ThoxClip trio.
- **Design.** Authenticated subscribers opt hardware in under epoch-bearing, revocable leases. Requests that exceed household capacity are placed on community stages by a first-fit contiguous planner under the two-domain admission rule (per-stage weights + KV must fit usable memory; a workspace reserve must remain; partial admission fails closed). Whole-request routing remains the preferred degenerate case.
- **Privacy.** KV and activations move only under principal-bound, attenuable, live grants; the coordinator sees metadata only and is never in the payload path; revocation crypto-shreds a principal's grant descendants. The paper states the binding limitation plainly: a stage holder sees the activations it computes on, and prompt-inversion research measures recovery from exactly those activations, so the community pool is specified for workloads the subscriber accepts exposing in activation form, and confidential workloads remain household-only until a measured defence exists.
- **Blockchain-like accounting, no inference cost.** Enrollments, lease epochs, grant events and MeshCredits are recorded in an append-only hash-chained ledger with batched Merkle anchoring, on the control plane only. Grant checks at inference time use a local signed epoch checkpoint. Lab-measured cost: 8.65 µs per ledger append, 18.44 µs per Merkle proof verification, and zero ledger operations per token or per activation.
- **Credits.** Contributors earn MeshCredits proportional to offered memory-time and completed work (lab example: 1 credit per GB-hour); subscribers spend credits or subscription grants; owner foreground work (P0) preempts contributed work and preempted stage-hours are not charged.

## Major workflows

### Read and cite the paper
Use `dist/` — PDF for reading, HTML for the web, DOCX for editing. Cite via `CITATION.cff`. Do not cite a DOI; none exists yet.

### Run the Virtual Lab
The lab (`exp/community_lab.py`, Python stdlib only) implements the specification at lab fidelity: planner, grant DAG, HMAC chunk keying, churn simulation, credits and ledger. `python3 exp/community_lab.py` prints the full evidence record; `exp/results/summary.json` is the file the paper was built from. `python3 exp/test_lab.py` runs the five unit tests.

### Verify a number from the paper
Find the claim in the paper's Table 1 or Sections 5/7, then find the same key in `exp/results/summary.json`. Evidence classes are printed with every result: CALCULATED (admission arithmetic), SIMULATED (lab drills and churn), LAB-MEASURED (micro-benchmarks on a general host — never device measurements), and MEASURED (household) for numbers reused from the household paper, DOI 10.5281/zenodo.23969070.

### Rebuild the paper
`wp/build_paper.py` reads only `summary.json` for lab numbers — there are no hand-typed results in the build. `wp/figures.py` regenerates Figures 4–5 from the same file; Figures 1–3 are TikZ diagrams whose sources are in `src/`.

## Configuration

The lab takes no configuration files. Model geometry, node pools, sequence length (4096) and the 20% workspace reserve are constants at the top of `exp/community_lab.py`; change them there and regenerate `summary.json` to explore other assumptions. Label any such run as your own — the paper's numbers are the committed ones.

## Troubleshooting

- **Tests fail on an older Python:** the lab uses `X | None` type syntax; use Python 3.10+.
- **PDF figures look small:** Figures 1–3 are dense TikZ diagrams; read them in the HTML edition or from `wp/figures/` at full resolution.
- **Numbers differ after a rebuild:** you changed a lab constant or a model geometry. Restore `exp/community_lab.py` and regenerate.

## FAQ

**Is the community mesh a shipped product?** No. This is a research specification and a lab. The paper's repository review (Section 6) records that multi-principal enrollment and credit accounting did not exist in any THOX repository at writing time.

**Is there a DOI?** Not yet. A Zenodo deposit is a separate founder-gated step.

**Is this the household MeshStack paper?** No — that is the predecessor, DOI 10.5281/zenodo.23969070, at https://github.com/ttracx/thox-meshstack-paper. This paper extends it from one household to a permissioned community.

**Why "blockchain-like" and not a blockchain?** The design needs tamper-evident history and verifiable credits, not distributed consensus. Consensus in the serving path would tax every request; the hash-chained ledger taxes only control-plane events.
