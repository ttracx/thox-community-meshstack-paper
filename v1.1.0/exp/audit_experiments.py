"""E1: audit predicates for contributed stage execution, on a real model.

A three-stage pipeline split of SmolLM2-135M-Instruct is emulated in one
process: stage boundaries serialise the residual stream to fp32 bytes and back
(the transport), and a SHA-256 chain over the boundary bytes is the stage
receipt. A "contributor" runs stage 2. We measure, per cheat class, how often
(a) a token-exact re-execution audit and (b) a boundary-digest audit detect
the cheat, and at which generated token the first divergence appears.

Greedy decoding, fixed prompts, fixed revision, no sampling. Timings are
medians over REPS repetitions after one warm-up run. Nothing else should run
on the host while this script is timing.

Writes exp/results/audit.json.
"""
from __future__ import annotations

import hashlib
import json
import platform
import statistics
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
NEW_TOKENS = 32
REPS = 2
STAGES = [(0, 10), (10, 20), (20, 30)]  # layer ranges; stage 2 is the contributor
SEED = 20261110

PROMPTS = [
    "Explain what a mesh network is in two sentences.",
    "Write a haiku about a quiet server room.",
    "List three uses for a spare laptop.",
    "What is the capital of Australia, and why is it not Sydney?",
    "Summarise the idea of a lease in distributed systems.",
    "Give me a recipe for scrambled eggs.",
    "Translate 'good morning, neighbour' into Spanish and French.",
    "Why do batteries degrade faster when they are hot?",
    "Describe the colour blue to someone who cannot see.",
    "What does a scheduler do in an operating system?",
    "Write one sentence that uses the words river, key and lantern.",
    "How many minutes are there in a week? Show the arithmetic.",
    "What is the difference between privacy and anonymity?",
    "Suggest a name for a community garden and explain it.",
    "Explain why the sky is dark at night.",
    "Draft a two-line thank-you note to a volunteer.",
    "What is a hash function used for?",
]


def load():
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, dtype=torch.float32).eval()
    return tok, model


class Pipeline:
    """Hook-based three-stage emulation with a receipt chain and optional cheats."""

    def __init__(self, model):
        self.model = model
        self.layers = model.model.layers
        self.handles = []
        self.chain = hashlib.sha256()
        self.boundary_bytes = 0
        self.noise_gen = None

    def clear(self):
        for h in self.handles:
            h.remove()
        self.handles = []
        self.chain = hashlib.sha256()
        self.boundary_bytes = 0

    def _boundary_hook(self, _mod, _inp, out):
        # Transport: fp32 little-endian bytes out, bytes back in. Receipt: hash chain.
        raw = out.detach().to(torch.float32).contiguous().numpy().tobytes()
        self.chain.update(raw)
        self.boundary_bytes += len(raw)
        return torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(out.shape).clone()

    def install(self, cheat: str | None):
        self.clear()
        lo, hi = STAGES[1]
        if cheat and cheat.startswith("skip"):
            k = int(cheat[4:])
            step = max(1, (hi - lo) // k)
            targets = list(range(lo + 1, hi, step))[:k] if k < (hi - lo) else list(range(lo, hi))

            def skip_hook(_mod, inp, _out):
                return inp[0]

            for i in targets:
                self.handles.append(self.layers[i].register_forward_hook(skip_hook))
        if cheat == "noise":
            self.noise_gen = torch.Generator().manual_seed(SEED)

            def noise_hook(_mod, _inp, out):
                rms = out.pow(2).mean().sqrt()
                return out + torch.randn(out.shape, generator=self.noise_gen) * rms * 1e-3

            self.handles.append(self.layers[hi - 1].register_forward_hook(noise_hook))
        # Boundary hooks go on last so the receipt covers what the stage actually emitted.
        for _, end in STAGES[:-1]:
            self.handles.append(self.layers[end - 1].register_forward_hook(self._boundary_hook))


def stage2_weight_cheat(model, kind: str):
    """Return a restore closure after replacing stage-2 weights with a cheaper form."""
    lo, hi = STAGES[1]
    saved = {}
    for i in range(lo, hi):
        for name, p in model.model.layers[i].named_parameters():
            if p.dim() < 2:
                continue
            saved[(i, name)] = p.data.clone()
            if kind == "fp16w":
                p.data = p.data.to(torch.float16).to(torch.float32)
            elif kind == "int8w":
                scale = p.data.abs().max() / 127.0
                p.data = (p.data / scale).round().clamp(-127, 127) * scale

    def restore():
        for (i, name), val in saved.items():
            dict(model.model.layers[i].named_parameters())[name].data = val

    return restore


def generate(tok, model, prompt: str) -> list[int]:
    msgs = [{"role": "user", "content": prompt}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True)
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=NEW_TOKENS, min_new_tokens=NEW_TOKENS, do_sample=False,
                             pad_token_id=tok.eos_token_id)
    return out[0, ids["input_ids"].shape[1]:].tolist()


def run_config(tok, model, pipe: Pipeline, cheat: str | None, staged: bool = True, time_it: bool = False):
    restore = None
    if cheat in ("fp16w", "int8w"):
        restore = stage2_weight_cheat(model, cheat)
    rows = []
    for prompt in PROMPTS:
        if staged:
            pipe.install(cheat)
        else:
            pipe.clear()
        t0 = time.perf_counter()
        toks = generate(tok, model, prompt)
        dt = time.perf_counter() - t0
        rows.append({"tokens": toks, "digest": pipe.chain.hexdigest() if staged else None,
                     "boundary_bytes": pipe.boundary_bytes if staged else 0, "seconds": dt if time_it else None})
    pipe.clear()
    if restore:
        restore()
    return rows


def first_divergence(a: list[int], b: list[int]) -> int | None:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None


def main() -> int:
    torch.manual_seed(SEED)
    torch.set_num_threads(2)
    tok, model = load()
    pipe = Pipeline(model)

    # Warm-up, then baselines.
    run_config(tok, model, pipe, None, staged=False)
    whole = run_config(tok, model, pipe, None, staged=False)
    honest = run_config(tok, model, pipe, None, staged=True)
    honest2 = run_config(tok, model, pipe, None, staged=True)

    # Determinism envelope on this host: same thread count twice, then one thread.
    torch.set_num_threads(1)
    honest_1t = run_config(tok, model, pipe, None, staged=True)
    torch.set_num_threads(2)

    cheats = ["skip1", "skip3", "skip10", "fp16w", "int8w", "noise"]
    results = {}
    for c in cheats:
        rows = run_config(tok, model, pipe, c, staged=True)
        divs = [first_divergence(h["tokens"], r["tokens"]) for h, r in zip(honest, rows)]
        results[c] = {
            "token_mismatch_prompts": sum(d is not None for d in divs),
            "digest_mismatch_prompts": sum(h["digest"] != r["digest"] for h, r in zip(honest, rows)),
            "first_divergence": divs,
        }

    # Timing: whole-model, staged honest, and digest-only verification cost.
    t_whole, t_staged = [], []
    for _ in range(REPS):
        t_whole.append(sum(r["seconds"] for r in run_config(tok, model, pipe, None, staged=False, time_it=True)))
        t_staged.append(sum(r["seconds"] for r in run_config(tok, model, pipe, None, staged=True, time_it=True)))

    n = len(PROMPTS)
    out = {
        "model": MODEL, "revision": REVISION, "layers": len(model.model.layers),
        "params": sum(p.numel() for p in model.parameters()),
        "stages": STAGES, "new_tokens": NEW_TOKENS, "prompts": n, "reps": REPS,
        "host": {"machine": platform.machine(), "python": platform.python_version(),
                 "torch": torch.__version__, "threads": 2},
        "staged_vs_whole_token_exact_prompts": sum(w["tokens"] == h["tokens"] for w, h in zip(whole, honest)),
        "honest_repeat_digest_equal_prompts": sum(a["digest"] == b["digest"] for a, b in zip(honest, honest2)),
        "honest_1thread_digest_equal_prompts": sum(a["digest"] == b["digest"] for a, b in zip(honest, honest_1t)),
        "honest_1thread_token_equal_prompts": sum(a["tokens"] == b["tokens"] for a, b in zip(honest, honest_1t)),
        "boundary_bytes_per_request_median": statistics.median(h["boundary_bytes"] for h in honest),
        "cheats": results,
        "seconds_whole_all_prompts": t_whole,
        "seconds_staged_all_prompts": t_staged,
    }
    Path(__file__).with_name("results").joinpath("audit.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "cheats"}, indent=1))
    for c, r in results.items():
        print(c, r["token_mismatch_prompts"], r["digest_mismatch_prompts"], r["first_divergence"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
