# Development handoff

- `lab/common.py`: RFC 9474 blind RSA, HPKE sealing, Ed25519, Merkle log, JSON-over-HTTP server with wire capture.
- `lab/services.py`: authority, coordinator, relay, stage node and auditor, cloud gateway, ledger, witness. One function per party; each runs as its own process.
- `lab/run_lab.py`: the requester's device and scenarios A to J. Add a scenario by appending to `sc[...]` with a `pass` field; `analyze.py` and the paper read from the evidence file.
- `exp/analyze.py` writes `summary.json`. Figures, paper, demo and README read only that file.
- Paper text lives in `wp/build.py`. Citations are `[@key]`; arXiv keys resolve from `wp/refs_raw.json` (run `wp/refs_fetch.py`), others from `MANUAL_REFS`.

Known limits to keep in mind when extending: hops are stateless; one auditor; the ledger's `/_lab_equivocate` endpoint is a test hook that plays a dishonest operator and must never exist in a product build; the stage node `/admin` endpoint stands in for the device owner's local switch.

Local checks (no GitHub Actions): `python3 -m lab.run_lab`, `python3 exp/token_experiments.py`, `node wp/qa.cjs`, `python3 wp/qa_pdf.py`.
