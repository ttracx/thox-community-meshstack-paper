"""E1 timing supplement: whole-model versus staged (boundary transport plus SHA-256 receipt chain)
generation time, REPS alternating passes after one warm-up. Updates exp/results/audit.json in place."""
from __future__ import annotations

import json
from pathlib import Path

import torch

import audit_experiments as A

REPS = 5


def main() -> int:
    torch.set_num_threads(2)
    tok, model = A.load()
    pipe = A.Pipeline(model)
    A.run_config(tok, model, pipe, None, staged=False)
    whole, staged = [], []
    for _ in range(REPS):
        whole.append(sum(r["seconds"] for r in A.run_config(tok, model, pipe, None, staged=False, time_it=True)))
        staged.append(sum(r["seconds"] for r in A.run_config(tok, model, pipe, None, staged=True, time_it=True)))
    path = Path(__file__).with_name("results") / "audit.json"
    out = json.loads(path.read_text())
    out["seconds_whole_all_prompts"], out["seconds_staged_all_prompts"], out["reps"] = whole, staged, REPS
    path.write_text(json.dumps(out, indent=1))
    print("whole", whole, "staged", staged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
