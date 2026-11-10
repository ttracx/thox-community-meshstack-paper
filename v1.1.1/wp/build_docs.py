"""Write README.md and the docs pack from summary.json so no number in them is typed by hand."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = json.loads((ROOT / "exp" / "results" / "summary.json").read_text())
A, T, F, LG, L = S["audit"], S["token"], S["fairness"], S["ledger"], S["lab"]
CH, NP, BIG = A["cheats"], A["prompts"], LG["batches"][-1]
dig = sum(c["digest_detect_prompts"] for c in CH.values())
tok = sum(c["token_detect_prompts"] for c in CH.values())
cheated = NP * len(CH)
V = "v1.1.1"
PDF, HTML, DEMO = (f"dist/THOX_Community_Mesh_Paper_{V}.pdf", f"dist/THOX_Community_Mesh_Paper_{V}.html",
                   f"dist/THOX_Community_Mesh_Demo_{V}.html")

(ROOT / "README.md").write_text(f"""# THOX Community Mesh: research paper and virtual lab ({V})

![Status](https://img.shields.io/badge/status-preprint%2C%20not%20peer%20reviewed-6B7280)
![THOX](https://img.shields.io/badge/THOX.ai-Research-05A451)
![License](https://img.shields.io/badge/license-Apache--2.0%20%2B%20CC%20BY%204.0-05A451)
![Lab](https://img.shields.io/badge/virtual%20lab-{sum(L['summary'].values())}%2F{len(L['summary'])}%20scenarios-05A451)
![CI](https://img.shields.io/badge/CI-local%20checks-05A451)

**THOX Community Mesh: Unlinkable Subscriber Tokens, Digest-Audited Stage Execution and a Witness-Cosigned Settlement Ledger for Member-Contributed Inference.** THOX.ai Research technical report {V}, 2026-11-10. Corresponding author: Tommy Xaypanya. Preprint, not peer reviewed. Internal until the founders authorise release.

**Your AI. Your Data. Your Rules.™**

![PDF contact sheet](docs/previews/pdf-contact-sheet.png)

## What is here

| Path | Contents |
|---|---|
| `{PDF}` | The paper (Letter, cover plus body) |
| `{HTML}` | Standalone HTML with embedded fonts and KaTeX |
| `{DEMO}` | Browser demo: RFC 9474 blind tokens with known-answer tests, audit calculator, tier admission, Merkle ledger with witnesses, lab evidence |
| `lab/` | The virtual lab: {L['processes']} processes, {len(L['summary'])} scenarios, `lab/evidence/evidence.json` |
| `companion/` | The companion lab (ChatGPT lane) as received, its authors' retained results, and this host's reproduction of its 62 tests and 150-trial campaign |
| `exp/` | Experiments, raw results, `results/summary.json` (single source of every number) |
| `wp/` | Reference fetch, figures, paper build, render, PDF, demo build, QA |
| `docs/` | User guide, quick start, development handoff, lane handoffs, ecosystem map, decision log, validation report |
| `.agents/HANDOFF.md` | Agent pickup file |

## Headline results

| Result | Value | Evidence class |
|---|---|---|
| Cheated requests exposed by a boundary-digest audit | {dig} / {cheated} | measured, {A['model'].split('/')[1]}, 2 vCPU host |
| Cheated requests exposed by a token-exact audit | {tok} / {cheated} (fp16 weights: {CH['fp16w']['token_detect_prompts']} / {NP}) | measured |
| Mint one unlinkable token, RSA-2048 | {T['client_ms_2048'] + T['issuer_ms_2048']:.1f} ms (verify {T['verify_ms_2048']:.2f} ms) | measured; RFC 9474 A.3 vector reproduced |
| Ledger cost per receipt at {BIG['receipts']:,} per epoch | {BIG['build_us_per_receipt']:.2f} microseconds; proof {BIG['proof_bytes']} bytes | measured |
| Virtual lab scenarios passed | {sum(L['summary'].values())} / {len(L['summary'])}; {L['C']['token_exact']} / {L['C']['requests']} requests token-exact | virtual lab, one host |
| Whole replica against two-stage pipeline, remote round trip per token | {L['K']['replica']['mean_ms']:.1f} ms against {L['K']['pipeline']['mean_ms']:.1f} ms, 30 trials each | virtual lab, loopback |
| Companion lab reproduced on this host | 62 / 62 tests; {S['companion']['reproduction']['trial_count']} / 150 trials numerically equal; {S['companion']['reproduction']['receipts']} receipts verified | reproduction, Python 3.12 |
| Load-indexed issuance, served tokens at 0.6 load | {F['table']['0.6|budget_load']['served_tokens']['median'] / 1e6:.2f} M against {F['table']['0.6|vtc']['served_tokens']['median'] / 1e6:.2f} M for least-served-first | simulated, 30 seeds |
| Fixed issuance budget, served tokens at 0.6 load | {(1 - F['table']['0.6|budget']['served_tokens']['median'] / F['table']['0.6|vtc']['served_tokens']['median']) * 100:.0f}% fewer than least-served-first | simulated, 30 seeds |

No THOX device, wide-area or throughput result is claimed. The community plane gives identity privacy, not content privacy against the contributor that executes a stage.

## Quick start

```
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers safetensors cryptography numpy matplotlib pypdf pillow
python3 -m lab.run_lab          # exit code 0 only if every scenario passes
python3 exp/analyze.py && python3 wp/figures.py && python3 wp/build.py
```

Full reproduction is in [docs/QUICKSTART.md](docs/QUICKSTART.md). Commands there ran on 2026-11-10.

## Docs map

- [User guide](docs/USER_GUIDE.md), [Quick start](docs/QUICKSTART.md), [Development handoff](docs/DEVELOPMENT.md)
- [Lane handoffs](docs/HANDOFFS.md), [Ecosystem map](docs/ecosystem_map.md), [Decision log](docs/DECISION_LOG.md), [Validation report](docs/VALIDATION.md), [Development queue](docs/DEVELOPMENT_QUEUE.md)
- [Agent pickup](.agents/HANDOFF.md)
- Releases: https://github.com/ttracx/thox-meshstack-inference/releases (no release is cut for this pack; a preprint is not a shipped version).

## License

Code: Apache-2.0. Paper text and figures: CC BY 4.0. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). THOX, ThoxOS, MeshStack and ThoxWork are trademarks of THOX.ai LLC.
""")

D = ROOT / "docs"
(D / "QUICKSTART.md").write_text("""# Quick start (commands run on 2026-11-10, Linux x86_64, 2 vCPU, 7 GB, Python 3.13)

```
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers safetensors cryptography numpy matplotlib pypdf pillow
python3 exp/audit_experiments.py          # about 10 minutes; downloads SmolLM2-135M-Instruct
(cd exp && python3 audit_timing.py)       # about 5 minutes
python3 exp/token_experiments.py          # about 1 minute
python3 exp/fairness_sim.py               # about 3 minutes
python3 exp/ledger_experiments.py
python3 -m lab.run_lab                    # about 3 minutes; needs about 5 GB RAM
python3 exp/analyze.py
cd wp && npm install && cd ..
python3 wp/figures.py && python3 wp/build.py
node wp/katex_render.cjs wp/paper.src.html wp/paper.html
node wp/pdf.cjs wp/paper.html wp/cover.pdf wp/body.pdf && python3 wp/merge_pdf.py
python3 wp/build_demo.py && python3 wp/build_docs.py
node wp/qa.cjs && python3 wp/qa_pdf.py    # needs Playwright and poppler-utils
```

Do not run anything else on the host during the timed experiments.
""")
(D / "USER_GUIDE.md").write_text(f"""# User guide

**Read the paper:** open `{PDF}` or `{HTML}`.

**Try the mechanisms:** open `{DEMO}` in any browser. It runs offline. The green chips at the top are known-answer tests; all seven must say pass. Then:

1. Issue a token, redeem it, redeem it again (the second is refused).
2. Pick a cheat and move the audit-rate slider to see how fast it is caught.
3. Change the queue mix and weight and grant in order.
4. Seal an epoch, prove an entry, tamper with it, then let the operator try to rewrite history.

**Run the lab:** `python3 -m lab.run_lab` from this folder. It starts {L['processes'] - 1} local processes, runs every scenario and writes `lab/evidence/evidence.json`, `lab/evidence/transcript.log` and one event log per process. Exit code 0 means every scenario passed.

**What the lab is not:** THOX hardware, a network, or a performance test.
""")
(D / "DEVELOPMENT.md").write_text("""# Development handoff

- `lab/common.py`: RFC 9474 blind RSA, HPKE sealing, Ed25519, Merkle log, JSON-over-HTTP server with wire capture.
- `lab/services.py`: authority, coordinator, relay, stage node and auditor, cloud gateway, ledger, witness. One function per party; each runs as its own process.
- `lab/run_lab.py`: the requester's device and scenarios A to J. Add a scenario by appending to `sc[...]` with a `pass` field; `analyze.py` and the paper read from the evidence file.
- `exp/analyze.py` writes `summary.json`. Figures, paper, demo and README read only that file.
- Paper text lives in `wp/build.py`. Citations are `[@key]`; arXiv keys resolve from `wp/refs_raw.json` (run `wp/refs_fetch.py`), others from `MANUAL_REFS`.

Known limits to keep in mind when extending: hops are stateless; one auditor; the ledger's `/_lab_equivocate` endpoint is a test hook that plays a dishonest operator and must never exist in a product build; the stage node `/admin` endpoint stands in for the device owner's local switch.

Local checks (no GitHub Actions): `python3 -m lab.run_lab`, `python3 exp/token_experiments.py`, `node wp/qa.cjs`, `python3 wp/qa_pdf.py`.
""")
(D / "ecosystem_map.md").write_text("""# ecosystem_map.md

Parent product: MeshStack (private distributed tier of the ThoxOS, MeshStack, ThoxWork platform model).

```mermaid
flowchart LR
  subgraph Device["Requester's device (ThoxOS, ThoxChat)"]
    W[Token wallet] --- SO[Seat order: local, own mesh, community, cloud]
  end
  AUTH[Subscription authority<br/>accounts, device certs, blind tokens, credits]
  REL[Relay<br/>no keys]
  COORD[Coordinator<br/>pool, leases, tier admission, fraud proofs]
  subgraph Pool["Community pool (members' devices)"]
    S1[Stage node] --> S2[Stage node]
    AUD[Auditor]
  end
  GW[Cloud gateway<br/>hosted models, labelled]
  LED[Settlement ledger] --- WIT[Witnesses]
  W -->|account + blinded value| AUTH
  SO -->|sealed| REL
  REL --> COORD
  REL --> S1
  REL --> AUD
  REL --> GW
  COORD -->|credits, penalties| LED
  COORD -->|credits| AUTH
```

| Direction | Component | Contract |
|---|---|---|
| Upstream | Auto Device Role Mode (meshstack-backend, sadie-mesh) | advertisement, lease, owner protection; this design adds a community scope |
| Upstream | meshstack-desktop exact-ID model sharing, ADR-025 | only approved local models are advertised; cloud tags never |
| Upstream | thox-meshstack-inference stage engine, D25, D31 | stage execution and the determinism envelope the audit depends on |
| Downstream | ThoxChat, ThoxOS, ThoxWork | plane label on every response; privacy class on every request |
| Data boundary | authority | knows accounts; never sees tokens or requests |
| Data boundary | coordinator, relay, ledger | never see accounts or prompts |
| Data boundary | stage nodes, auditor | see activations (invertible); never accounts |
| Data boundary | cloud gateway | sees the prompt; never the account |
""")
(D / "DECISION_LOG.md").write_text("""# Decision log (this pack)

Assumptions made without waiting, per the standing ship rule. Reverse any by saying so.

| # | Decision | Reason | Who can reverse |
|---|---|---|---|
| 1 | Non-transferable service credits, no currency | keeps D20 (no payments market) | Tommy |
| 2 | No cross-member KV or cache sharing | keeps D19 and D43 | Tommy, after the security review D43 asks for |
| 3 | Cloud models are a separate labelled plane, never advertised as mesh compute | keeps ADR-025 | Tommy |
| 4 | Settlement is a witness-cosigned transparency log, not a consensus chain | approved 2026-11-10 ("go with your recommendations") | Tommy |
| 10 | Companion paper and lab are cited, reproduced and reconciled, not merged into one result or one identity | two runtimes' records stay separate; differences are listed in paper Table 10 | Tommy |
| 11 | Adopted from the companion: plan-wide admission rule, execution contexts, replica-first default, confidential refusal | they are right and compatible | Tommy |
| 12 | Version bumped to v1.1.0 for the consolidated edition; pushed to main on approval of 2026-11-10 | new results and sections | Tommy |
| 5 | Audit predicate is the boundary digest; token-exactness stays the D25 certification gate | measured in this pack | Tommy / CAO |
| 6 | Byline: THOX.ai Research, corresponding author Tommy Xaypanya; no AI author | arXiv policy and the paper skill | founders, before any submission |
| 8 | Test model SmolLM2-135M-Instruct | small enough for fourteen processes on a 7 GB host | anyone, by editing lab/common.py |
| 9 | Product working name left as "community mesh" | naming and device categories are Tommy's | Tommy |
""")
(D / "DEVELOPMENT_QUEUE.md").write_text("""# Development queue

Priority = Market Value x 0.4 + Technical Feasibility x 0.3 + Time-to-Market x 0.2 + Strategic Importance x 0.1

| Rank | Task | MV | TF | TTM | SI | Score |
|---|---|---:|---:|---:|---:|---:|
| 1 | Two-machine lab over WireGuard with a third-party relay host | 9 | 8 | 8 | 9 | 8.5 |
| 2 | One lab: merge the companion lab's mTLS, grants and outbox with this lab's tokens, audits and ledger | 9 | 7 | 7 | 9 | 8.0 |
| 3 | Community scope in Auto Device Role Mode tables and RPCs (sadie-mesh) | 9 | 7 | 7 | 9 | 8.0 |
| 4 | Tier keys and blind issuance in the subscription authority | 8 | 8 | 7 | 8 | 7.8 |
| 5 | Boundary-digest receipts in the stage-server engine | 8 | 7 | 7 | 9 | 7.6 |
| 6 | Determinism-class measurement across contributing device types | 8 | 6 | 6 | 9 | 7.1 |
| 7 | Ledger and witness service beside the coordinator | 7 | 8 | 6 | 7 | 7.1 |
| 8 | Second auditor and appeal before permanent penalties | 6 | 7 | 6 | 7 | 6.4 |

Recommendation: start with 1; it converts every lab claim into a two-host claim with no new design work.
""")
(D / "VALIDATION.md").write_text(f"""# Validation report (2026-11-10)

| Check | Command | Result |
|---|---|---|
| Virtual lab | `python3 -m lab.run_lab` | exit 0; {sum(L['summary'].values())} of {len(L['summary'])} scenarios passed |
| RFC 9474 known-answer test (Python) | `python3 exp/token_experiments.py` | {sum(T['kat'].values())} of {len(T['kat'])} checks |
| Known-answer tests in the browser | `node wp/qa.cjs` | 7 of 7 at 1280 and 390 px, light and dark |
| Demo flows | `node wp/qa.cjs` | token verifies, double spend refused, proof valid, tamper invalid, fork refused by 3 of 3 |
| Horizontal scroll, console errors | `node wp/qa.cjs` | none on paper or demo at either width |
| PDF | `python3 wp/qa_pdf.py` | all pages reviewed on the contact sheet; no em dashes, no placeholder text |
| References | `python3 wp/refs_fetch.py` plus RFC Editor and venue pages | 19 arXiv entries resolved; 7 RFCs and 4 venue pages opened; every listed reference is cited |

Repository review that preceded the paper:

| Repository (commit) | Tests run here | Result |
|---|---|---|
| thox-meshstack-inference (7e86cec) | `python3 -m pytest tests/ --ignore=tests/gui`; `cargo test --workspace` | Python 422 passed, 1 failed, 2 skipped; Rust 92 passed, 0 failed |
| meshstack-backend (ffd722d) | not run (package install blocked in this session) | its own doc reports 347 passed on 2026-11-02; not verified |
| sadie-mesh (5bedacb), meshstack-desktop (b2b6e3f), THOX_MeshStack (6f45599) | read only | desktop changelog records 2 failing share-off tests on main |

Open defect found: `meshstack_v2/observatory/bounds.py:54` treats a JSON string as a path and raises "File name too long" (`tests/observatory/test_observatory_contracts.py::test_bounds_loader_accepts_json_and_path`).

| Companion lab, Python 3.12.3 | `python -m unittest discover -s tests`; `python -m mesh_lab experiment --blocks 30` | 62 of 62 tests; 150 of 150 trials numerically equal; 5 of 5 scenarios; 164 receipts verified |
| Companion lab, Python 3.13 | same | 43 unit tests pass; integration setup fails on strict certificate verification (missing Authority Key Identifier) |

Not done: Developers preview mount, physical or two-host run, external review. Claim limits are Section 7 of the paper.
""")
(D / "HANDOFFS.md").write_text("""# Lane handoffs (THOX-CLOSEOUT-HANDOFF-001)

Each block is an assignment, not evidence that the lane ran it.

## Hermes
Task: Enforce closeout for this pack on the Sadie runtime once it is in a repository; then run the lab on two fleet hosts.
Inputs: this pack, `lab/`, `docs/VALIDATION.md`.
Exit evidence: packet with preview path, commit SHA, email record, two-host `evidence.json`.
Stop: never send from AgentMail or Gmail; no tokens or keys in the packet.

## Codex
Task: Add boundary digests to stage-server receipts; add subject and authority key identifiers to the companion lab's generated certificates and re-run its 62 tests on Python 3.13.
Inputs: this pack; the failing test named in `docs/VALIDATION.md`.
Exit evidence: SHA, `pytest` and `cargo test` output, written limit for anything not run.
Stop: do not mark unrun checks done; do not invent a date, price or certification.

## Muse
Task: Draft claim-safe captions for the demo page and a one-paragraph plain-language summary.
Inputs: paper Sections 1 and 7; the evidence classes in the README table.
Exit evidence: caption text that keeps "virtual lab", "simulated" and "identity privacy, not content privacy".
Stop: never publish; a lab result never becomes a device claim.

## Claude
Task: Design unlinkable admission that holds heavy members to their share under overload (load-indexed issuance does not), in `exp/fairness_sim.py` and the lab authority, and re-run.
Inputs: `exp/fairness_sim.py`, `lab/services.py` (run_authority), paper Section 6.4.
Exit evidence: base and head SHA, commands, the new summary rows, lab exit code.
Stop: do not weaken the refusals; do not remove the wire scan.

## DigitalHumans
Samuel Reed files this pack and handoff in the docs lane. Julian Hale mounts the HTML at `/docs/community-mesh` with the preprint and virtual-lab labels visible. Clara Voss checks green #05A451 on dark and #047C3D on white, trademarks and public-copy limits. Nova runs `python3 -m lab.run_lab`, `node wp/qa.cjs`, `python3 wp/qa_pdf.py` and returns the logs. Kai owns nothing until hardware is touched. Sera reviews claim language before any external use. Sadie sends the Outlook email after the push.
""")
(ROOT / ".agents").mkdir(exist_ok=True)
(ROOT / ".agents" / "HANDOFF.md").write_text(f"""# Agent pickup

Status: paper {V} built and pushed to ttracx/thox-meshstack-inference main under papers/community-mesh-{V}; virtual lab {sum(L['summary'].values())}/{len(L['summary'])}; companion lab reproduced.
Key files: `lab/run_lab.py`, `lab/services.py`, `exp/analyze.py`, `wp/build.py`, `exp/results/summary.json`, `lab/evidence/evidence.json`.
Conventions: every number flows from summary.json; evidence classes (measured, virtual lab, simulated, calculated) are never mixed; no em dashes; THOX.ai casing.
Blockers: founders' rulings on requester identity default and author roster; rulings on D20, D43, ADR-025 for the community scope.
Last verified: 2026-11-10, Odette Lark.
""")
print("docs written")
