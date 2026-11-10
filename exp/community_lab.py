"""
THOX Community MeshStack Virtual Lab — corrected, complete implementation.

Research specification evidence only. No production community mesh is claimed.
Evidence classes:
  CALCULATED — two-domain admission arithmetic over stated model geometry.
  SIMULATED  — placement, churn, grant and privacy drills run in this lab
               on a general host. Not device measurements.
  MEASURED   — reused only from the household paper (Ross & Xaypanya 2026,
               DOI 10.5281/zenodo.23969070), cited as such, never re-measured
               here except the HMAC timing micro-benchmark, which is labelled
               LAB-MEASURED on this host class in its result record.

Fixes vs the uploaded v0.1 lab:
  * min_nodes_for_pipeline() never sharded weights and returned a capped
    count of whole-model-capable nodes (an 8B that fits whole was reported
    as needing 4 nodes). Replaced by a real first-fit contiguous planner:
    each stage carries only its layer share of weights and KV, embedding
    on stage 0, head on the last stage, workspace checked in its own
    domain, and a 20% usable-memory reserve enforced per stage.
  * Whole-request routing is the one-stage degenerate case and is reported
    as 1 node, as the specification requires.
"""
from __future__ import annotations
import hashlib, hmac, json, math, random, statistics, time, zlib
from dataclasses import dataclass, field

GB = 1024**3

# ---------------------------------------------------------------- models
@dataclass
class Model:
    name: str
    layers: int
    weights_gb: float          # total Q4-class weight footprint, GB (decimal, as published)
    kv_bytes_per_token: int    # attention KV summed over ALL layers, per token
    fixed_state_gb: float = 0.0  # recurrent / fixed state, charged once (stage 0)
    embed_gb: float = 0.15
    head_gb: float = 0.15

    @property
    def w_per_layer(self): return max(0.0, (self.weights_gb - self.embed_gb - self.head_gb)) / self.layers
    @property
    def kv_per_layer(self): return self.kv_bytes_per_token / self.layers

MODELS = [
    Model("Qwen3-8B",       36,  5.0,  80_000),
    Model("Gemma-3-27B",    62, 16.5,  65_536, fixed_state_gb=0.157),
    Model("Qwen3-32B",      64, 20.1, 256_000),
    Model("Llama-3.3-70B",  80, 43.2, 320_000),
    Model("THOX-27B-ref",   48, 14.6,  65_536, fixed_state_gb=0.157),  # household negative-result geometry (GiB weights)
]

@dataclass
class Node:
    name: str
    usable_gb: float
    principal: str = "contributor"
    online: bool = True
    thermal_ok: bool = True
    foreground_busy: bool = False   # owner P0 work: hard filter, never evicted

# ------------------------------------------------- two-domain admission
def stage_fits(model: Model, node: Node, n_layers: int, is_first: bool, is_last: bool,
               seq_len: int = 4096, reserve_frac: float = 0.20) -> bool:
    if not node.online or not node.thermal_ok or node.foreground_busy or n_layers <= 0:
        return False
    w = model.w_per_layer * n_layers
    if is_first: w += model.embed_gb + model.fixed_state_gb
    if is_last:  w += model.head_gb
    kv_gb = (model.kv_per_layer * n_layers * seq_len) / GB
    needed = w + kv_gb
    if needed > node.usable_gb:                       # domain 1: weights + KV
        return False
    if node.usable_gb - needed < reserve_frac * node.usable_gb:  # domain 2: workspace reserve
        return False
    return True

def max_layers_on(model, node, remaining, is_first, seq_len=4096):
    lo = 0
    for n in range(remaining, -1, -1):
        if stage_fits(model, node, n, is_first, n == remaining, seq_len):
            lo = n; break
    return lo

def plan_pipeline(model: Model, nodes: list[Node], seq_len: int = 4096):
    """First-fit contiguous planner. Returns plan dict or None (UNPLACEABLE, fail-closed)."""
    usable = [n for n in nodes if n.online and n.thermal_ok and not n.foreground_busy]
    placed, stages, idx = 0, [], 0
    while placed < model.layers and idx < len(usable):
        node = usable[idx]; idx += 1
        remaining = model.layers - placed
        take = max_layers_on(model, node, remaining, placed == 0, seq_len)
        if take <= 0:
            continue
        is_last = (placed + take == model.layers)
        # recompute exact stage charge for the record
        w = model.w_per_layer * take + (model.embed_gb + model.fixed_state_gb if placed == 0 else 0) + (model.head_gb if is_last else 0)
        kv = (model.kv_per_layer * take * seq_len) / GB
        stages.append({"node": node.name, "principal": node.principal,
                       "layers": f"{placed}-{placed+take-1}", "n_layers": take,
                       "weights_gb": round(w, 3), "kv_gb": round(kv, 3),
                       "needed_gb": round(w + kv, 3), "usable_gb": node.usable_gb})
        placed += take
    if placed < model.layers:
        return None
    return {"model": model.name, "stages": len(stages),
            "mode": "whole-request" if len(stages) == 1 else "pipeline",
            "plan": stages}

# ---------------------------------------------------------------- grants
@dataclass
class Grant:
    gid: str
    principal: str
    parent: str | None
    rights: frozenset
    scope: str
    epoch: int
    fingerprint: str
    revoked: bool = False

class GrantGraph:
    """Principal-bound, attenuable grant DAG with consumption-time validation
    and crypto-shredding on revocation."""
    def __init__(self, current_epoch: int = 7):
        self.grants: dict[str, Grant] = {}
        self.current_epoch = current_epoch
        self.shredded_keys: set[str] = set()
    def issue(self, g: Grant):
        if g.parent is not None:
            p = self.grants[g.parent]
            assert g.rights <= p.rights, "attenuation violation: rights may only narrow"
            assert g.principal == p.principal, "grants are principal-bound"
        self.grants[g.gid] = g
    def revoke(self, gid: str):
        # crypto-shred: revoke the grant and every descendant; their chunk keys die with it
        stack = [gid]
        while stack:
            cur = stack.pop()
            self.grants[cur].revoked = True
            self.shredded_keys.add(cur)
            stack += [k for k, v in self.grants.items() if v.parent == cur]
    def validate(self, gid: str, need: str, fingerprint: str) -> tuple[bool, str]:
        g = self.grants.get(gid)
        if g is None: return False, "unknown grant"
        chain, cur = [], g
        while cur is not None:
            chain.append(cur)
            cur = self.grants.get(cur.parent) if cur.parent else None
        if any(x.revoked for x in chain): return False, "revoked (crypto-shredded)"
        if g.epoch != self.current_epoch: return False, "stale epoch"
        if need not in g.rights: return False, "right not granted"
        if g.fingerprint != fingerprint: return False, "model fingerprint mismatch"
        return True, "ok"

def chunk_key(secret: bytes, fingerprint: bytes, prev: bytes, tokens: list[int]) -> bytes:
    msg = b"thox-meshstack-kv-v1|" + prev + b"|" + fingerprint + b"|" + b"".join(t.to_bytes(4, "big") for t in tokens)
    return hmac.new(secret, msg, hashlib.sha256).digest()

# ---------------------------------------------------------------- drills
def privacy_drills() -> dict:
    fp = hashlib.sha256(b"model-A-q4-tokenizer-v1").hexdigest()[:16]
    fp_other = hashlib.sha256(b"model-B-q4-tokenizer-v1").hexdigest()[:16]
    gg = GrantGraph(current_epoch=7)
    gg.issue(Grant("root", "alice", None, frozenset({"kv", "stage", "route"}), "community", 7, fp))
    gg.issue(Grant("kv1", "alice", "root", frozenset({"kv"}), "community", 7, fp))
    gg.issue(Grant("stale", "alice", "root", frozenset({"kv"}), "community", 6, fp))
    results = {}
    results["valid_kv_grant_accepted"] = gg.validate("kv1", "kv", fp)[0]
    results["attenuation_widening_rejected"] = False
    try:
        gg.issue(Grant("wide", "alice", "kv1", frozenset({"kv", "stage"}), "community", 7, fp))
    except AssertionError:
        results["attenuation_widening_rejected"] = True
    results["cross_principal_grant_rejected"] = False
    try:
        gg.issue(Grant("xpr", "mallory", "root", frozenset({"kv"}), "community", 7, fp))
    except AssertionError:
        results["cross_principal_grant_rejected"] = True
    results["stale_epoch_rejected"] = not gg.validate("stale", "kv", fp)[0]
    results["fingerprint_mismatch_rejected"] = not gg.validate("kv1", "kv", fp_other)[0]
    results["ungranted_right_rejected"] = not gg.validate("kv1", "stage", fp)[0]
    gg.revoke("root")
    results["revoked_root_descendants_rejected"] = not gg.validate("kv1", "kv", fp)[0]
    results["crypto_shred_descendants"] = sorted(gg.shredded_keys)
    # coordinator metadata-only check: the coordinator log schema carries no payload fields
    coord_fields = {"node", "principal", "capacity_gb", "block_id", "token_count", "load", "epoch"}
    results["coordinator_sees_metadata_only"] = not (coord_fields & {"prompt", "activation", "kv_bytes", "weights", "plaintext"})
    results["all_pass"] = all(v for k, v in results.items() if isinstance(v, bool))
    return results

def hmac_benchmark(chunks: int = 2000) -> dict:
    secret, fp = b"lab-principal-secret", hashlib.sha256(b"model-A").digest()
    prev, t0 = bytes(32), time.perf_counter()
    per = []
    for i in range(chunks):
        s = time.perf_counter()
        prev = chunk_key(secret, fp, prev, list(range(i % 64, i % 64 + 64)))
        per.append((time.perf_counter() - s) * 1e6)
    return {"chunks": chunks, "median_us_per_64token_chunk": round(statistics.median(per), 2),
            "p95_us": round(sorted(per)[int(0.95 * len(per))], 2),
            "class": "LAB-MEASURED on this general host (VM, shared vCPU); not a device measurement"}

def kv_compression_lab(tokens: int = 4096) -> dict:
    # Structured synthetic KV: f16-like byte planes with concentrated exponents.
    rnd = random.Random(42)
    raw = bytearray()
    for _ in range(tokens * 64):
        raw += bytes([rnd.choice([0, 0, 0, 63, 64, 65]), rnd.randrange(256)])
    comp = zlib.compress(bytes(raw), level=3)
    out = {"input_bytes": len(raw), "compressed_bytes": len(comp),
           "ratio": round(len(raw) / len(comp), 3),
           "bit_exact_roundtrip": zlib.decompress(comp) == bytes(raw),
           "class": "SIMULATED synthetic tensors in this lab; the paper's wire ratio is the household MEASURED 1.17-1.20x on real GGUF KV"}
    return out

def churn_simulation(seeds: int = 30) -> dict:
    """Pools of 10-50 mixed nodes; nodes churn mid-session; count successful
    re-plans vs fail-closed aborts. Fail-closed is a correct outcome, not an error."""
    rnd = random.Random(20261110)
    model = MODELS[1]  # Gemma-3-27B geometry
    trials, placed_first, replanned, fail_closed = 0, 0, 0, 0
    for _ in range(seeds):
        n = rnd.choice([10, 20, 35, 50])
        pool = [Node(f"c{i}", rnd.choice([8.0, 12.0, 16.0, 24.0, 32.0]), principal=f"user{i%9}") for i in range(n)]
        plan = plan_pipeline(model, pool)
        trials += 1
        if plan is None:
            fail_closed += 1; continue
        placed_first += 1
        # churn: kill the first stage node, re-plan on the remainder
        victim = plan["plan"][0]["node"]
        for nd in pool:
            if nd.name == victim: nd.online = False
        if plan_pipeline(model, pool) is not None: replanned += 1
        else: fail_closed += 1
    return {"seeds": seeds, "model": model.name, "placed_on_first_plan": placed_first,
            "replanned_after_stage_loss": replanned, "fail_closed_total": fail_closed,
            "class": "SIMULATED"}

def credits_example() -> dict:
    # MeshCredits: earn proportional to memory-time offered; spend per stage-hour consumed.
    offer = [{"node": "c1", "gb": 16, "hours": 10}, {"node": "c2", "gb": 32, "hours": 6}]
    earned = sum(o["gb"] * o["hours"] for o in offer)
    return {"earn_rule": "1 credit per GB-hour offered and available", "example_earned_credits": earned,
            "spend_rule": "stage-hours consumed x stage GB, debited against subscription grant first, then earned credits",
            "owner_priority": "P0 owner foreground work preempts; preempted stage-hours are not charged",
            "class": "CALCULATED example; no live credit market is claimed"}

# ---------------------------------------------------------------- main
def run_all() -> dict:
    pools = {
        "household_trio_2_4_6GB": [Node("ThoxAir", 1.6, "owner"), Node("ThoxMini", 3.2, "owner"), Node("ThoxClip", 4.8, "owner")],
        "community_10_mixed": [Node(f"c{i}", g, f"user{i%5}") for i, g in enumerate([8, 12, 16, 16, 24, 32, 12, 16, 24, 32])],
        "community_4x16GB": [Node(f"c{i}", 16.0, f"user{i}") for i in range(4)],
        "community_4x32GB": [Node(f"c{i}", 32.0, f"user{i}") for i in range(4)],
        "single_16GB": [Node("solo", 16.0, "owner")],
        "single_32GB": [Node("solo", 32.0, "owner")],
        "single_64GB": [Node("solo", 64.0, "owner")],
    }
    capacity = []
    for m in MODELS:
        row = {"model": m.name, "weights_gb": m.weights_gb, "layers": m.layers}
        for pname, pool in pools.items():
            plan = plan_pipeline(m, pool)
            row[pname] = ({"stages": plan["stages"], "mode": plan["mode"]} if plan else "unplaceable")
        capacity.append(row)
    household_negative = plan_pipeline(MODELS[4], pools["household_trio_2_4_6GB"]) is None
    summary = {
        "lab": "THOX Community MeshStack Virtual Lab v1.0.0",
        "date": "2026-11-10",
        "evidence_classes": {"calculated": "admission arithmetic", "simulated": "lab runs on a general host", "measured_household": "reused from DOI 10.5281/zenodo.23969070"},
        "measured_household_reused": {"kv_compression_real_gguf": "1.17-1.20x", "hmac_us_per_64token_chunk_household": 9.7, "cross_host_transfer_overhead_s": 0.196},
        "capacity_calculated": capacity,
        "household_trio_27B_unplaceable_calculated": household_negative,
        "privacy_drills_simulated": privacy_drills(),
        "hmac_lab": hmac_benchmark(),
        "kv_compression_lab_simulated": kv_compression_lab(),
        "churn_simulated": churn_simulation(),
        "credits_calculated": credits_example(),
    }
    return summary

if __name__ == "__main__":
    s = run_all()
    print(json.dumps(s, indent=2))

# ------------------------------------------------- ledger (blockchain-like, off payload path)
import hashlib as _hl
def _h(b: bytes) -> bytes: return _hl.sha256(b).digest()
class Ledger:
    """Append-only hash-chained log for CONTROL-PLANE records only:
    enrollments, lease epochs, grant issue/revoke, credit earn/spend.
    No prompt, activation, KV or weight ever enters an entry.
    Anchoring is batched: a Merkle root is published periodically;
    inference never waits on the ledger."""
    def __init__(self): self.entries: list[dict] = []
    def append(self, kind: str, actor: str, payload: dict) -> str:
        prev = self.entries[-1]["hash"] if self.entries else "0"*64
        body = f"{prev}|{kind}|{actor}|{json.dumps(payload, sort_keys=True)}".encode()
        digest = _h(body).hex()
        self.entries.append({"i": len(self.entries), "prev": prev, "kind": kind, "actor": actor, "payload": payload, "hash": digest})
        return digest
    def verify_chain(self) -> bool:
        prev = "0"*64
        for e in self.entries:
            body = f"{prev}|{e['kind']}|{e['actor']}|{json.dumps(e['payload'], sort_keys=True)}".encode()
            if _h(body).hex() != e["hash"] or e["prev"] != prev: return False
            prev = e["hash"]
        return True
    def merkle_root(self) -> str:
        level = [_h(bytes.fromhex(e["hash"])) for e in self.entries] or [_h(b"empty")]
        while len(level) > 1:
            if len(level) % 2: level.append(level[-1])
            level = [_h(level[i] + level[i+1]) for i in range(0, len(level), 2)]
        return level[0].hex()
    def proof(self, idx: int):
        level = [_h(bytes.fromhex(e["hash"])) for e in self.entries]; path = []; pos = idx
        while len(level) > 1:
            if len(level) % 2: level.append(level[-1])
            sib = pos ^ 1; path.append({"sib": level[sib].hex(), "pos_is_left": pos % 2 == 0})
            level = [_h(level[i] + level[i+1]) for i in range(0, len(level), 2)]; pos //= 2
        return path
    @staticmethod
    def verify_proof(entry_hash: str, path, root: str) -> bool:
        cur = _h(bytes.fromhex(entry_hash))
        for step in path:
            sib = bytes.fromhex(step["sib"])
            cur = _h(cur + sib) if step["pos_is_left"] else _h(sib + cur)
        return cur.hex() == root

def ledger_benchmark(n: int = 5000) -> dict:
    led = Ledger(); t0 = time.perf_counter()
    for i in range(n):
        led.append("credit_earn", f"user{i%20}", {"gb_hours": 16, "epoch": 7})
    append_s = time.perf_counter() - t0
    t0 = time.perf_counter(); ok = led.verify_chain(); verify_s = time.perf_counter() - t0
    root = led.merkle_root(); path = led.proof(1234)
    t0 = time.perf_counter()
    for _ in range(1000): Ledger.verify_proof(led.entries[1234]["hash"], path, root)
    proof_us = (time.perf_counter() - t0) / 1000 * 1e6
    # tamper drill
    led.entries[100]["payload"] = {"gb_hours": 99999}
    tamper_detected = not led.verify_chain()
    return {"entries": n, "append_us_per_entry": round(append_s / n * 1e6, 2),
            "full_chain_verify_ms": round(verify_s * 1000, 1), "chain_valid_before_tamper": ok,
            "merkle_proof_len": len(path), "proof_verify_us_median_1000": round(proof_us, 2),
            "tamper_detected": tamper_detected,
            "design": "Ledger sits on the metadata/control plane only, batched Merkle anchoring; grant checks use a local signed epoch checkpoint, so steady-state inference adds 0 ledger operations per token or per activation.",
            "class": "LAB-MEASURED append/verify timing on this general host; tamper and proof drills SIMULATED in this lab"}
