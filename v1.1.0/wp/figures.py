"""Generate every paper figure as SVG from exp/results/summary.json.

Fonts are referenced by name (svg.fonttype none) so the HTML embeds them.
Colors: THOX green #047C3D on white, ink #111827, greys. No number is typed
here; everything is read from summary.json.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
S = json.loads((ROOT / "exp" / "results" / "summary.json").read_text())
FIG = ROOT / "wp" / "figures"
FIG.mkdir(exist_ok=True)

GREEN, GREEN2, INK, GREY, LIGHT, AMBER = "#047C3D", "#05A451", "#111827", "#6B7280", "#C7CCD4", "#B45309"
plt.rcParams.update({
    "svg.fonttype": "none", "font.family": "Inter", "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "600",
    "axes.labelsize": 9, "axes.edgecolor": GREY, "axes.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "xtick.labelsize": 8, "ytick.labelsize": 8, "xtick.color": GREY, "ytick.color": GREY,
    "legend.fontsize": 8, "legend.frameon": False, "figure.dpi": 100,
})
CHEAT_LABEL = {"skip1": "skip 1 of 10 layers", "skip3": "skip 3 of 10 layers", "skip10": "skip the whole stage",
               "fp16w": "fp16 weights", "int8w": "int8 weights", "noise": "0.1% output noise"}


def save(fig, name: str):
    fig.savefig(FIG / name, format="svg", bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def fig_audit():
    A = S["audit"]
    names = list(A["cheats"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 3.0), gridspec_kw={"width_ratios": [1.05, 1]})
    y = np.arange(len(names))
    a.barh(y - 0.19, [A["cheats"][n]["digest_detect_rate"] * 100 for n in names], 0.36, color=GREEN, label="boundary-digest audit")
    a.barh(y + 0.19, [A["cheats"][n]["token_detect_rate"] * 100 for n in names], 0.36, color=LIGHT, label="token-exact audit")
    a.set_yticks(y, [CHEAT_LABEL[n] for n in names])
    a.invert_yaxis()
    a.set_xlim(0, 100)
    a.set_xlabel("audited requests exposed (%)")
    a.set_title("Detection per audited request")
    a.legend(loc="upper center", bbox_to_anchor=(0.4, -0.2), ncol=2)
    t = np.arange(1, A["new_tokens"] + 1)
    styles = {"skip1": (INK, "-"), "skip3": (GREY, "-"), "skip10": (GREEN, "-"), "fp16w": (AMBER, "--"),
              "int8w": (GREEN2, "--"), "noise": (INK, ":")}
    for n in names:
        c, ls = styles[n]
        b.plot(t, np.array(A["cheats"][n]["prefix_detection_curve"]) * 100, color=c, ls=ls, lw=1.4, label=CHEAT_LABEL[n])
    b.set_ylim(-3, 103)
    b.set_xlabel("generated tokens re-executed by a token-exact audit")
    b.set_ylabel("requests exposed (%)")
    b.set_title("Token-exact audit needs a long prefix")
    b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    save(fig, "fig_audit.svg")


def fig_detect():
    A = S["audit"]
    fig, ax = plt.subplots(figsize=(7.4, 3.3))
    n = np.arange(1, 501)
    d = A["weakest_token_detect_rate"]
    for q, c in zip((0.01, 0.05, 0.10, 0.25), (LIGHT, GREY, GREEN2, GREEN)):
        ax.plot(n, 1 - (1 - q) ** n, color=c, lw=1.6, label=f"digest audit, q = {q:g}")
    if d > 0:
        ax.plot(n, 1 - (1 - 0.10 * d) ** n, color=AMBER, lw=1.4, ls="--",
                label=f"token-exact audit, q = 0.1, weakest cheat ({CHEAT_LABEL[A['weakest_cheat_for_token_audit']]})")
    else:
        ax.plot(n, np.zeros_like(n, dtype=float), color=AMBER, lw=1.4, ls="--",
                label=f"token-exact audit, any q, weakest cheat ({CHEAT_LABEL[A['weakest_cheat_for_token_audit']]})")
    ax.axhline(0.99, color=INK, lw=0.6, ls=":")
    ax.set_xscale("log")
    ax.set_xlabel("requests served by a contributor that cheats on every request")
    ax.set_ylabel("probability caught")
    ax.set_title("Sampled audits catch a persistent cheat quickly; the audit predicate matters more than the rate")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    save(fig, "fig_detect.svg")


def fig_token():
    T = S["token"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 2.8))
    phases = ["blind", "blind_sign", "finalize", "verify"]
    labels = ["blind\n(client)", "blind-sign\n(issuer)", "finalise\n(client)", "verify\n(redeemer)"]
    x = np.arange(4)
    for i, (r, c) in enumerate(zip(T["blind_rsa"], (GREEN, LIGHT))):
        vals = [r[p]["median_ms"] for p in phases]
        a.bar(x + (i - 0.5) * 0.36, vals, 0.36, color=c, label=f"RSA-{r['bits']} (n = {r['runs']})")
        for xi, v in zip(x, vals):
            a.text(xi + (i - 0.5) * 0.36, v * 1.12, f"{v:.2f}" if v < 10 else f"{v:.0f}", ha="center", fontsize=6.5, color=INK)
    a.set_yscale("log")
    a.set_xticks(x, labels)
    a.set_ylabel("median time (ms, log)")
    a.set_title("Blind-signed token, per phase")
    a.set_ylim(top=a.get_ylim()[1] * 2)
    a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    sizes = [h["payload_bytes"] for h in T["hpke"]]
    b.plot(sizes, [h["seal_median_us"] for h in T["hpke"]], color=GREEN, marker="o", ms=4, lw=1.5, label="seal")
    b.plot(sizes, [h["open_median_us"] for h in T["hpke"]], color=INK, marker="s", ms=4, lw=1.5, ls="--", label="open")
    b.set_xscale("log", base=2)
    b.set_yscale("log")
    b.set_xlabel("payload (bytes)")
    b.set_ylabel("median time (microseconds, log)")
    b.set_title(f"Sealed envelope (HPKE), +{T['hpke_overhead_bytes']} bytes per message")
    b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    save(fig, "fig_token.svg")


def fig_fairness():
    F = S["fairness"]
    loads = F["params"]["loads"]
    pols = [("fifo", "FIFO", LIGHT, "-"), ("vtc", "least-served-first", GREY, "-"),
            ("vtc_contrib", "contribution-weighted", GREEN, "-"), ("budget", "fixed issuance budget (unlinkable)", AMBER, "--"),
            ("budget_load", "load-indexed budget (unlinkable)", GREEN2, "--")]
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.9))
    for ax, key, title in zip(axes[:2], ("contributors_p95_wait_s", "others_p95_wait_s"),
                              ("Contributors: p95 wait", "Other members: p95 wait")):
        for pol, lab, c, ls in pols:
            m = [F["table"][f"{l}|{pol}"][key]["median"] for l in loads]
            lo = [F["table"][f"{l}|{pol}"][key]["q1"] for l in loads]
            hi = [F["table"][f"{l}|{pol}"][key]["q3"] for l in loads]
            ax.plot(loads, np.maximum(m, 0.5), color=c, ls=ls, marker="o", ms=3, lw=1.5, label=lab)
            ax.fill_between(loads, np.maximum(lo, 0.5), np.maximum(hi, 0.5), color=c, alpha=0.15, lw=0)
        ax.set_yscale("log")
        ax.set_xlabel("offered load / pool capacity")
        ax.set_title(title)
    axes[0].set_ylabel("seconds (log), median and IQR of 30 seeds")
    ax = axes[2]
    for pol, lab, c, ls in pols:
        ax.plot(loads, [F["table"][f"{l}|{pol}"]["heavy_service_share"]["median"] * 100 for l in loads], color=c, ls=ls,
                marker="o", ms=3, lw=1.5, label=lab)
    ax.axhline(F["heavy_demand_share"] * 100, color=INK, lw=0.6, ls=":")
    ax.text(loads[0], F["heavy_demand_share"] * 100 + 0.8, "their share of demand", fontsize=7, color=INK)
    ax.set_xlabel("offered load / pool capacity")
    ax.set_title("Two heavy members: share of service (%)")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=3)
    save(fig, "fig_fairness.svg")


def fig_ledger():
    L = S["ledger"]
    big = L["batches"][-1]
    items = [("witness verify, 5 cosignatures (per epoch)", big["cosign_verify_us"]["median"]),
             ("witness cosign, 5 signatures (per epoch)", big["cosign_us"]["median"]),
             ("receipt verify, Ed25519 (per hop)", L["receipt_verify_us"]["median"]),
             ("receipt sign, Ed25519 (per hop)", L["receipt_sign_us"]["median"]),
             (f"inclusion proof verify ({big['receipts']:,} receipts)", big["proof_verify_us"]["median"]),
             ("Merkle build (per receipt)", big["build_us_per_receipt"])]
    fig, ax = plt.subplots(figsize=(7.4, 2.4))
    y = np.arange(len(items))
    ax.barh(y, [v for _, v in items], color=[LIGHT, LIGHT, GREEN, GREEN, GREEN2, GREEN2], height=0.6)
    for yi, (_, v) in zip(y, items):
        ax.text(v * 1.15, yi, f"{v:,.1f} µs", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(y, [k for k, _ in items])
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlim(0.3, max(v for _, v in items) * 8)
    ax.set_xlabel("median cost (microseconds, log)")
    ax.set_title("Settlement ledger costs; none of them sits between two generated tokens")
    save(fig, "fig_ledger.svg")


def fig_topology():
    K, N, C = S["lab"]["K"], S["network"], S["companion"]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(7.4, 3.6), gridspec_kw={"width_ratios": [0.8, 1.25, 1.25]})
    names = ["pipeline", "replica"]
    means = [K[n]["mean_ms"] for n in names]
    err = [[m - K[n]["ci95_ms"][0] for m, n in zip(means, names)], [K[n]["ci95_ms"][1] - m for m, n in zip(means, names)]]
    a.bar(["two-stage\npipeline", "whole\nreplica"], means, color=[LIGHT, GREEN], yerr=err, capsize=3, error_kw={"lw": 0.8})
    for i, m in enumerate(means):
        a.text(i, m + 4, f"{m:.0f} ms", ha="center", fontsize=7.5)
    a.set_ylim(0, max(means) * 1.25)
    a.set_ylabel("remote round trip per token (ms)")
    a.set_title("This lab (measured)")
    x = np.arange(len(N["rows"]))
    b.bar(x - 0.2, [r["pipeline_tok_s"] for r in N["rows"]], 0.4, color=LIGHT, label="pipeline via relay")
    b.bar(x + 0.2, [r["replica_tok_s"] for r in N["rows"]], 0.4, color=GREEN, label="whole replica via relay")
    b.axhline(N["rows"][0]["hosted_stream_tok_s"], color=INK, lw=0.6, ls=":")
    b.text(len(x) - 0.5, N["rows"][0]["hosted_stream_tok_s"] + 0.6, "compute only", fontsize=7, ha="right")
    b.set_xticks(x, [r["link"].replace(" ", "\n") for r in N["rows"]], fontsize=7)
    b.set_ylabel("tokens per second, one stream")
    b.set_title("Link sensitivity (calculated)")
    b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=1)
    labels = {"replica_0ms": "replica", "pipeline_0ms": "pipeline", "pipeline_5ms": "+5 ms", "pipeline_15ms": "+15 ms",
              "pipeline_audit_paused": "audit\npaused"}
    xs = np.arange(len(C["retained"]["configurations"]))
    for off, tag, col, lab in ((-0.2, "retained", LIGHT, "authors' host"), (0.2, "reproduction", GREEN, "this host")):
        cfg = C[tag]["configurations"]
        m = [q["mean_inter_token_ms"] for q in cfg]
        e = [[q["mean_inter_token_ms"] - q["inter_token_mean_ci95_ms"][0] for q in cfg],
             [q["inter_token_mean_ci95_ms"][1] - q["mean_inter_token_ms"] for q in cfg]]
        c.bar(xs + off, m, 0.4, color=col, yerr=e, capsize=2, error_kw={"lw": 0.8}, label=lab)
    c.set_xticks(xs, [labels[q["configuration"]] for q in C["retained"]["configurations"]], fontsize=7)
    c.set_ylabel("inter-token interval (ms)")
    c.set_title("Companion lab, reproduced")
    c.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=2)
    fig.tight_layout()
    save(fig, "fig_topology.svg")


if __name__ == "__main__":
    fig_topology()
    fig_audit()
    fig_detect()
    fig_token()
    fig_fairness()
    fig_ledger()
