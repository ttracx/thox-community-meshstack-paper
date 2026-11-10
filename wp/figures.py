"""Figures from exp/results/summary.json only. THOX green #05A451 sole accent."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
S = json.loads((ROOT / "exp/results/summary.json").read_text())
OUT = ROOT / "wp/figures"; OUT.mkdir(parents=True, exist_ok=True)
GREEN = "#05A451"; GRAY = "#9CA3AF"; INK = "#111827"
plt.rcParams.update({"font.size": 9, "text.color": INK, "axes.edgecolor": GRAY})

rows = S["capacity_calculated"]
labels = [r["model"] for r in rows]
pools = ["single_16GB", "community_4x16GB", "community_4x32GB", "single_64GB"]
pool_names = ["Single 16 GB", "Community 4x16 GB", "Community 4x32 GB", "Single 64 GB"]
fig, ax = plt.subplots(figsize=(7.2, 3.4))
x = range(len(labels)); w = 0.19
for i, (p, pn) in enumerate(zip(pools, pool_names)):
    vals = [(r[p]["stages"] if isinstance(r[p], dict) else 0) for r in rows]
    bars = ax.bar([j + (i - 1.5) * w for j in x], vals, width=w,
                  color=GREEN if i in (1, 2) else GRAY, label=pn)
    for b, v, r in zip(bars, vals, rows):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.12,
                str(v) if v else "x", ha="center", fontsize=7.5)
ax.set_xticks(list(x)); ax.set_xticklabels(labels, fontsize=8)
ax.set_ylabel("Pipeline stages required (0 = unplaceable)")
ax.set_title("Figure 4. Stages required by pool (CALCULATED, seq 4096, 20% reserve)", fontsize=9, color=INK)
ax.legend(fontsize=7.5, frameon=False); ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "fig4_capacity.png", dpi=220); plt.close(fig)

ch = S["churn_simulated"]
fig, ax = plt.subplots(figsize=(3.6, 2.8))
ax.bar(["Placed", "Re-planned\nafter stage loss", "Fail-closed"], 
       [ch["placed_on_first_plan"], ch["replanned_after_stage_loss"], ch["fail_closed_total"]],
       color=[GREEN, GREEN, GRAY])
ax.set_title("Figure 5. Churn simulation, 30 seeds (SIMULATED)", fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "fig5_churn.png", dpi=220); plt.close(fig)
print("figures written")
