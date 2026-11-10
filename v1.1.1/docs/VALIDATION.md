# Validation report (2026-11-10)

| Check | Command | Result |
|---|---|---|
| Virtual lab | `python3 -m lab.run_lab` | exit 0; 12 of 12 scenarios passed |
| RFC 9474 known-answer test (Python) | `python3 exp/token_experiments.py` | 5 of 5 checks |
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
