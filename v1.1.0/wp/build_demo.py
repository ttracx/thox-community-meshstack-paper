"""Embed summary.json and the RFC 9474 test vector into the demo page; write dist/THOX_Community_Mesh_Demo_v1.1.0.html."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v1.1.0"
S = json.loads((ROOT / "exp" / "results" / "summary.json").read_text())
vec = json.loads((ROOT / "exp" / "rfc9474_a3.json").read_text())["vector"]
slim = {
    "kat_vector": {k: vec[k] for k in ("p", "q", "n", "e", "d", "prepared_msg", "salt", "inv", "encoded_msg", "blinded_msg", "blind_sig", "sig")},
    "audit": {k: S["audit"][k] for k in ("model", "prompts", "new_tokens")} | {
        "cheats": {n: {k: c[k] for k in ("token_detect_rate", "digest_detect_rate")} for n, c in S["audit"]["cheats"].items()}},
    "token": {k: S["token"][k] for k in ("client_ms_2048", "issuer_ms_2048", "verify_ms_2048")},
    "ledger": {"batches": [{k: b[k] for k in ("receipts", "build_us_per_receipt", "proof_bytes")} for b in S["ledger"]["batches"]]},
    "fairness": {"params": {"loads": S["fairness"]["params"]["loads"]}, "table": {
        key: {k: {"median": row[k]["median"]} for k in ("contributors_p95_wait_s", "others_p95_wait_s", "heavy_service_share")}
        for key, row in S["fairness"]["table"].items()}},
    "lab": S["lab"],
}
tpl = (ROOT / "wp" / "demo_template.html").read_text()
out = tpl.replace("/*__SUMMARY__*/", json.dumps(slim).replace("</", "<\\/")).replace("__VERSION__", VERSION)
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "THOX_Community_Mesh_Demo_v1.1.0.html").write_text(out)
print("wrote demo", round(len(out) / 1e3, 1), "KB")
