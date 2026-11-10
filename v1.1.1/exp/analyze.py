"""Reduce raw experiment and lab outputs to exp/results/summary.json.

summary.json is the single source of every number in the paper, the figures
and the demo. Nothing downstream types a number by hand.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "exp" / "results"


def load(name: str) -> dict:
    return json.loads((R / name).read_text())


def med_iqr(xs: list[float]) -> dict:
    q = statistics.quantiles(xs, n=4)
    return {"median": statistics.median(xs), "q1": q[0], "q3": q[2]}


def binom_tail(n: int, a: float, r: int) -> float:
    return sum(math.comb(n, k) * a ** k * (1 - a) ** (n - k) for k in range(r, n + 1))


def main() -> int:
    S: dict = {}

    # ---------------- E1 audit predicates on a real model
    A = load("audit.json")
    n = A["prompts"]
    cheats = {}
    for name, c in A["cheats"].items():
        divs = [d for d in c["first_divergence"] if d is not None]
        curve = [sum(1 for d in divs if d < t) / n for t in range(1, A["new_tokens"] + 1)]
        cheats[name] = {
            "token_detect_rate": c["token_mismatch_prompts"] / n, "token_detect_prompts": c["token_mismatch_prompts"],
            "digest_detect_rate": c["digest_mismatch_prompts"] / n, "digest_detect_prompts": c["digest_mismatch_prompts"],
            "first_divergence_median": statistics.median(divs) if divs else None,
            "prefix_detection_curve": curve,
        }
    t_whole = statistics.median(A["seconds_whole_all_prompts"]) / n
    t_staged = statistics.median(A["seconds_staged_all_prompts"]) / n
    S["audit"] = {
        "model": A["model"], "revision": A["revision"], "params_m": A["params"] / 1e6, "layers": A["layers"],
        "stages": A["stages"], "prompts": n, "new_tokens": A["new_tokens"], "reps": A["reps"], "host": A["host"],
        "staged_token_exact": A["staged_vs_whole_token_exact_prompts"],
        "repeat_digest_equal": A["honest_repeat_digest_equal_prompts"],
        "one_thread_digest_equal": A["honest_1thread_digest_equal_prompts"],
        "one_thread_token_equal": A["honest_1thread_token_equal_prompts"],
        "boundary_kib_per_request": A["boundary_bytes_per_request_median"] / 1024,
        "seconds_per_request_whole": t_whole, "seconds_per_request_staged": t_staged,
        "staging_overhead_pct": (t_staged / t_whole - 1) * 100,
        "cheats": cheats,
    }
    # detection arithmetic: P(detect within n requests) = 1 - (1 - q d)^n
    rates = [0.01, 0.05, 0.10, 0.25]
    worst_token = min((c["token_detect_rate"] for c in cheats.values()))
    weak = min(cheats, key=lambda k: cheats[k]["token_detect_rate"])
    det = []
    for q in rates:
        row = {"q": q, "digest_n99": math.ceil(math.log(0.01) / math.log(1 - q))}
        d = cheats[weak]["token_detect_rate"]
        row["token_weakest_n99"] = math.ceil(math.log(0.01) / math.log(1 - q * d)) if d > 0 else None
        det.append(row)
    S["audit"]["weakest_cheat_for_token_audit"] = weak
    S["audit"]["weakest_token_detect_rate"] = worst_token
    S["audit"]["requests_to_99pct"] = det
    # deterrence: cheating does not pay when q d L > (1 - q d) g  =>  q > g / (d (L + g))
    S["audit"]["min_audit_rate_for_deterrence"] = [
        {"loss_over_gain": k, "q_min_digest": 1 / (k + 1)} for k in (10, 100, 1000)]

    # ---------------- E2 tokens and sealed envelope
    T = load("token.json")
    S["token"] = {"kat": T["kat_rfc9474_a3"], "kat_all": all(T["kat_rfc9474_a3"].values()),
                  "blind_rsa": T["blind_rsa"], "hpke": T["hpke"],
                  "client_ms_2048": T["blind_rsa"][0]["blind"]["median_ms"] + T["blind_rsa"][0]["finalize"]["median_ms"],
                  "issuer_ms_2048": T["blind_rsa"][0]["blind_sign"]["median_ms"],
                  "verify_ms_2048": T["blind_rsa"][0]["verify"]["median_ms"],
                  "hpke_overhead_bytes": T["hpke"][0]["overhead_bytes"]}

    # ---------------- E3 admission simulation
    F = load("fairness.json")
    params = F["params"]
    table = {}
    for load_ in params["loads"]:
        for pol in ("fifo", "vtc", "vtc_contrib", "budget", "budget_load"):
            runs = [r for r in F["runs"] if r["load"] == load_ and r["policy"] == pol]
            table[f"{load_}|{pol}"] = {
                "contributors_p95_wait_s": med_iqr([r["contributors"]["p95_wait_s"] for r in runs]),
                "others_p95_wait_s": med_iqr([r["others"]["p95_wait_s"] for r in runs]),
                "heavy_p95_wait_s": med_iqr([r["heavy"]["p95_wait_s"] for r in runs]),
                "heavy_service_share": med_iqr([r["heavy_service_share"] for r in runs]),
                "served_tokens": med_iqr([r["served_tokens"] for r in runs]),
                "surplus_tokens": med_iqr([r.get("surplus_tokens", 0.0) for r in runs]),
            }
    S["fairness"] = {
        "params": params, "table": table,
        "heavy_demand_share": params["heavy_factor"] * params["heavy_members"] /
                              (params["members"] - params["heavy_members"] + params["heavy_factor"] * params["heavy_members"]),
        "owner_delay_max_s": max(r["owner_delay_max_s"] for r in F["runs"]),
        "owner_returns_total": sum(r["owner_returns"] for r in F["runs"]),
        "worst_chunk_s": params["worst_chunk_s"],
    }

    # ---------------- E4 settlement ledger
    S["ledger"] = load("ledger.json")

    # ---------------- E5 availability (closed form)
    avail = []
    for a in (0.5, 0.67, 0.8, 0.9):
        row = {"availability": a}
        for r in (1, 2):
            n_s = r
            while binom_tail(n_s, a, r) ** 2 < 0.99:   # two remote stages, independent
                n_s += 1
            row[f"enrolled_per_stage_r{r}"] = n_s
        avail.append(row)
    S["availability"] = {"target": 0.99, "remote_stages": 2, "rows": avail}

    # ---------------- virtual lab evidence
    L = json.loads((ROOT / "lab" / "evidence" / "evidence.json").read_text())
    sc = L["scenarios"]
    S["lab"] = {
        "all_pass": L["all_pass"], "summary": L["summary"], "host": L["host"], "processes": len(L["processes"]) + 1,
        "A": {k: sc["A_enrolment"][k] for k in ("forged_certificate_advert", "non_subscriber_enrol", "cloud_model_tag_advert", "pool_size", "nodes")},
        "B": {k: v for k, v in sc["B_tokens"].items()},
        "C": {k: v for k, v in sc["C_inference"].items() if k != "rows"},
        "D": sc["D_owner_protection"], "E": sc["E_contributor_death"], "F": sc["F_audit"], "G": sc["G_admission"],
        "H": sc["H_cloud_plane"], "I": sc["I_information_flow"], "J": sc["J_ledger"],
        "K": {k: v for k, v in sc["K_replica_vs_pipeline"].items() if k != "trials"},
        "Lx": sc["L_load_indexed_issuance"],
    }

    # ---------------- E6 decode-cycle network model (calculated)
    # Companion paper form: T = T_compute + (link traversals) * d + (bytes on links) / g.
    links = [("Nearby LAN", 1e-3, 1000e6 / 8), ("Metro", 10e-3, 100e6 / 8), ("WAN", 30e-3, 50e6 / 8),
             ("Constrained WAN", 60e-3, 10e6 / 8)]
    comp = 0.040
    check = [(comp + 4 * d + (3 * 16384 + 4) / g) * 1e3 for _, d, g in links]      # companion Table 5 inputs
    hidden_bytes = 576 * 4 + S["token"]["hpke_overhead_bytes"]                    # one fp32 position, sealed
    receipt = S["ledger"]["receipt_bytes"] + S["ledger"]["signature_bytes"]
    rows = []
    for name, d, g in links:
        # pipeline through the relay: device-relay-stage1-stage2 and back the same way: 6 traversals
        pipe_bytes = 3 * hidden_bytes + 3 * (hidden_bytes + 2 * receipt)
        # whole remote replica through the relay: device-relay-replica and back: 4 traversals
        rep_bytes = 2 * hidden_bytes + 2 * (hidden_bytes + receipt)
        tp = comp + 6 * d + pipe_bytes / g
        tr = comp + 4 * d + rep_bytes / g
        rows.append({"link": name, "one_way_ms": d * 1e3, "mbps": g * 8 / 1e6, "pipeline_ms": tp * 1e3,
                     "replica_ms": tr * 1e3, "pipeline_tok_s": 1 / tp, "replica_tok_s": 1 / tr,
                     "hosted_stream_tok_s": 1 / comp})
    S["network"] = {"compute_s_assumed": comp, "companion_table5_reproduced_ms": check,
                    "hidden_position_bytes": hidden_bytes, "receipt_bytes": receipt, "rows": rows}

    # ---------------- companion lab (ChatGPT lane): retained results and this host's reproduction
    comp_dir = ROOT / "companion"
    S["companion"] = {}
    for tag in ("retained", "reproduction"):
        cs = json.loads((comp_dir / tag / "summary.json").read_text())
        env = json.loads((comp_dir / tag / "environment.json").read_text())
        av = json.loads((comp_dir / tag / "audit-verification.json").read_text())
        S["companion"][tag] = {
            "python": env["python"].split()[0], "model_fingerprint": env["model"]["fingerprint"],
            "parameters": env["model"]["parameter_count"], "plan_sha256": cs["plan_sha256"],
            "trial_count": cs["trial_count"], "warmups": cs["warmups"],
            "scenario_passes": cs["scenario_passes"], "scenario_count": cs["scenario_count"],
            "receipts": av["receipts"], "chain_ok": av["ok"],
            "configurations": [{k: c[k] for k in ("configuration", "completed", "numerically_equal", "mean_inter_token_ms",
                                                   "inter_token_mean_ci95_ms", "inter_token_trial_mean_cv_percent",
                                                   "mean_ttft_ms", "mean_settlement_commit_ms", "d37_dispersion_condition")}
                               for c in cs["configurations"]],
        }
    S["companion"]["tests_reproduced"] = {"python312": "62 tests OK (43 unit, 19 integration)",
                                          "python313": "43 unit OK; integration setup fails: certificate verify failed, Missing Authority Key Identifier"}
    S["companion"]["same_model_bits"] = (S["companion"]["retained"]["model_fingerprint"] ==
                                         S["companion"]["reproduction"]["model_fingerprint"])
    S["companion"]["same_plan"] = S["companion"]["retained"]["plan_sha256"] == S["companion"]["reproduction"]["plan_sha256"]
    (R / "summary.json").write_text(json.dumps(S, indent=1))
    print("wrote summary.json; lab all_pass =", L["all_pass"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
