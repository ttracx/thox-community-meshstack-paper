"""THOX community mesh virtual lab: start every party, run every scenario, write evidence.

Usage:  python3 -m lab.run_lab            (from the paper root)

Ten operating-system processes on loopback: authority, coordinator, relay, four
contributor stage nodes (B1, B2 hold layers 10-19; C1, C2 hold layers 20-29),
one auditor, one cloud gateway, and this process, which is the subscriber's
own device (layers 0-9, embeddings and output head stay local).

Evidence goes to lab/evidence/evidence.json with a readable transcript in
lab/evidence/transcript.log. Every claim in the paper that cites the lab is a
field of that JSON file.
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path

if mp.current_process().name == "MainProcess":   # spawned parties must not pay for the model libraries
    import numpy as np
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

from . import services as S
from .common import (MODEL, MODEL_FP, REVISION, STAGES, Sealer, Signer, b64, blind, canon, finalize, merkle_verify,
                     post, seal, sha, token_verify, unb64, verify, wait_up)

BASE = 18200
PORTS = {"authority": BASE, "coordinator": BASE + 1, "relay": BASE + 2, "B1": BASE + 11, "B2": BASE + 12,
         "R1": BASE + 13, "C1": BASE + 21, "C2": BASE + 22, "A1": BASE + 31, "gateway": BASE + 41, "ledger": BASE + 51,
         "W1": BASE + 61, "W2": BASE + 62, "W3": BASE + 63}
ACCOUNTS = {
    "bearer-alice-7f3a91": {"member": "m_alice", "subscriber": True},    # contributes B1
    "bearer-bob-2c8e44": {"member": "m_bob", "subscriber": True},        # contributes B2
    "bearer-carol-9d1b07": {"member": "m_carol", "subscriber": True},    # contributes C1 and C2
    "bearer-dana-5a6f23": {"member": "m_dana", "subscriber": True},      # consumes only
    "bearer-erin-e04c58": {"member": "m_erin", "subscriber": True},      # consumes only, heavy
    "bearer-thox-audit-1b7d": {"member": "m_thox_audit", "subscriber": True},
    "bearer-mallory-0000aa": {"member": "m_mallory", "subscriber": False},
}
BEARER = {a["member"]: b for b, a in ACCOUNTS.items()}
CANARY = "zebra-quartz-lighthouse-4471"
PROMPTS = [
    "Explain what a mesh network is in two sentences.",
    "List three uses for a spare laptop.",
    "Summarise the idea of a lease in distributed systems.",
    "Why do batteries degrade faster when they are hot?",
    "What is the difference between privacy and anonymity?",
    "What is a hash function used for?",
    "Give two reasons to back up your files.",
    "Explain fairness to a ten-year-old.",
]
OUT = Path(__file__).resolve().parent / "evidence"
LOG: list[str] = []


def say(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    LOG.append(line)
    print(line, flush=True)


class Device:
    """The subscriber's own device: local plane, token wallet and sealed transport."""

    def __init__(self):
        torch.set_num_threads(1)
        self.tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        self.model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, dtype=torch.float32).eval()
        lo, hi = STAGES["s0"]
        self.s0 = [self.model.model.layers[i] for i in range(lo, hi)]
        self.authority = post(PORTS["authority"], "/info", {})[1]
        self.akeys = {t: (int(k["n"]), k["e"]) for t, k in self.authority["keys"].items()}
        self.coord = post(PORTS["coordinator"], "/info", {})[1]
        self.gateway = post(PORTS["gateway"], "/info", {})[1]
        self.relay_bytes = 0
        self.token_msgs: list[bytes] = []

    # ---- tokens: blind, have the authority sign, unblind, check
    def get_tokens(self, member: str, tier: str, count: int, aud: str):
        n, e = self.akeys[tier]
        msgs = [os.urandom(32).hex().encode() + f"|aud={aud}".encode() for _ in range(count)]
        blinded = [blind(n, e, m) for m in msgs]
        code, out = post(PORTS["authority"], "/issue", {"bearer": BEARER[member], "tier": tier,
                                                         "blinded": [str(z) for z, _ in blinded]})
        if code != 200:
            return code, out
        toks = []
        for m, (_, inv), bs in zip(msgs, blinded, out["blind_sigs"]):
            sig = finalize(n, int(bs), inv)
            assert token_verify(n, e, m, sig)
            self.token_msgs.append(m)
            toks.append({"msg": b64(m), "sig": b64(sig), "tier": tier})
        return 200, toks

    # ---- every remote call is sealed to its recipient and sent through the relay
    def sealed(self, to: str, pub: str, obj: dict) -> tuple[int, dict]:
        reply = Sealer()
        body = b64(seal(pub, {**obj, "reply_pub": reply.pub}))
        self.relay_bytes += len(body)
        code, out = post(PORTS["relay"], "/forward", {"to": to, "body": body}, timeout=180.0)
        if code == 200 and "body" in out:
            return 200, reply.open(unb64(out["body"]))
        return code, out

    def coordinator(self, obj: dict) -> dict:
        return self.sealed("coordinator", self.coord["hpke_pub"], obj)[1]

    # ---- local computation
    def whole(self, prompt: str, n: int = S.MAX_NEW_TOKENS) -> list[int]:
        ids = self.tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                           return_tensors="pt", return_dict=True)
        with torch.no_grad():
            g = self.model.generate(**ids, max_new_tokens=n, min_new_tokens=n, do_sample=False,
                                    pad_token_id=self.tok.eos_token_id)
        return g[0, ids["input_ids"].shape[1]:].tolist()

    def local_front(self, ids: list[int]):
        with torch.no_grad():
            h = self.model.model.embed_tokens(torch.tensor([ids]))
        return S._run_layers(torch, self.s0, self.model.model.rotary_emb, h)

    def local_head(self, h_last) -> int:
        with torch.no_grad():
            logits = self.model.lm_head(self.model.model.norm(h_last))[0, -1]
        logits[self.tok.eos_token_id] = float("-inf")   # same rule as min_new_tokens in the whole-model baseline
        return int(logits.argmax())

    # ---- one request on the community plane
    def community_generate(self, prompt: str, lease: dict, audit_q: float = 0.0, rng: random.Random | None = None,
                           on_step=None, submit_fraud: bool = True, n_tokens: int = S.MAX_NEW_TOKENS) -> dict:
        ids = self.tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                           return_tensors="pt", return_dict=True)["input_ids"][0].tolist()
        new, receipts, events, audits = [], [], [], []
        step, t0 = 0, time.perf_counter()
        hop_ms = []
        while step < n_tokens:
            if on_step:
                on_step(step)
            route = lease["lease"]["route"]
            h = self.local_front(ids + new)
            raw = h.contiguous().numpy().tobytes()
            a = time.perf_counter()
            code, out = self.sealed(route[0]["node_id"], route[0]["hpke_pub"],
                                    {"op": "hop", "lease": lease, "step": step, "h": b64(raw), "shape": list(h.shape)})
            hop_ms.append((time.perf_counter() - a) * 1e3)
            if code != 200:
                failed = out.get("hop") or route[0]["node_id"]
                events.append({"step": step, "event": "hop_failed", "node": failed, "code": code,
                               "error": out.get("error")})
                lease = self.coordinator({"op": "reroute", "lease_id": lease["lease"]["lease_id"], "exclude": [failed]})
                if "lease" not in lease:
                    return {"error": lease.get("error", "reroute_failed"), "events": events, "tokens": new}
                events.append({"step": step, "event": "rerouted", "route": [x["node_id"] for x in lease["lease"]["route"]]})
                continue
            rcs = out["receipts"]
            h_raw = unb64(out["h"])
            chain_ok = (len(rcs) == len(route)
                        and all(verify(r_["sign_pub"], rc["body"], rc["sig"]) for r_, rc in zip(route, rcs))
                        and rcs[0]["body"]["in_digest"] == sha(raw)
                        and all(b["body"]["in_digest"] == a["body"]["out_digest"] for a, b in zip(rcs, rcs[1:]))
                        and rcs[-1]["body"]["out_digest"] == sha(h_raw)
                        and all(rc["body"]["step"] == step and rc["body"]["plan_digest"] == lease["lease"]["plan_digest"]
                                for rc in rcs))
            if not chain_ok:
                return {"error": "receipt_chain_invalid", "events": events, "tokens": new}
            if rng is not None and rng.random() < audit_q:
                _, res = self.sealed("A1", self.auditor_pub, {"op": "audit", "h": b64(raw), "shape": list(h.shape),
                                                               "receipts": rcs})
                bad = [f for f in res["findings"] if not f["finding"]["match"]]
                audits.append({"step": step, "match": [f["finding"]["match"] for f in res["findings"]]})
                if bad:
                    f = bad[0]
                    rc = next(r for r in rcs if r["body"]["node_id"] == f["finding"]["node_id"])
                    events.append({"step": step, "event": "audit_mismatch", "node": f["finding"]["node_id"]})
                    if submit_fraud:
                        acc = self.coordinator({"op": "fraud", "proof": {"receipt": rc, **f}})
                        events.append({"step": step, "event": "fraud_proof", "accepted": acc.get("accepted")})
                        lease = self.coordinator({"op": "reroute", "lease_id": lease["lease"]["lease_id"],
                                                  "exclude": [f["finding"]["node_id"]]})
                        if "lease" not in lease:
                            return {"error": "reroute_failed", "events": events, "tokens": new}
                        events.append({"step": step, "event": "rerouted_and_restarted", "tokens_discarded": len(new),
                                       "route": [x["node_id"] for x in lease["lease"]["route"]]})
                        new, receipts, step = [], [], 0    # nothing the cheater touched is kept
                        continue
                    return {"detected_at_step": step, "events": events, "audits": audits, "tokens": new, "lease": lease}
            receipts += rcs
            h_last = torch.from_numpy(np.frombuffer(h_raw, dtype=np.float32).copy()).reshape(out["shape"])
            new.append(self.local_head(h_last))
            step += 1
        closed = self.coordinator({"op": "close", "lease_id": lease["lease"]["lease_id"], "receipts": receipts})
        return {"tokens": new, "text": self.tok.decode(new), "events": events, "audits": audits,
                "seconds": time.perf_counter() - t0, "hop_ms_median": statistics.median(hop_ms),
                "hop_ms_mean": statistics.fmean(hop_ms), "hop_ms_first": hop_ms[0],
                "receipts": len(receipts), "closed": closed, "final_route": [x["node_id"] for x in lease["lease"]["route"]]}

    def lease(self, member: str, tier: str = "base", **flags) -> dict:
        code, toks = self.get_tokens(member, tier, 1, "community")
        if code != 200:
            return {"error": toks.get("error")}
        return self.coordinator({"op": "lease", "token": toks[0], **flags})


def rss_mb(pid: int) -> float:
    for line in open(f"/proc/{pid}/status"):
        if line.startswith("VmRSS"):
            return round(int(line.split()[1]) / 1024, 1)
    return 0.0


def start(name: str, target, *args):
    p = mp.Process(target=target, args=args, daemon=True, name=name)
    p.start()
    return p


def main() -> int:
    mp.set_start_method("spawn", force=True)
    OUT.mkdir(exist_ok=True)
    ev: dict = {"lab": "THOX community mesh virtual lab", "date": time.strftime("%Y-%m-%d"),
                "scope": "fifteen OS processes on one host over loopback; real cryptography and a real model; "
                         "no THOX hardware, no wide-area network, no production service",
                "model": MODEL, "revision": REVISION, "model_fp": MODEL_FP, "stages": STAGES,
                "host": {"machine": platform.machine(), "python": platform.python_version(),
                         "torch": torch.__version__, "cpus": os.cpu_count()}, "scenarios": {}}
    procs = {}
    say("starting authority, coordinator, relay")
    procs["authority"] = start("authority", S.run_authority, PORTS["authority"], ACCOUNTS,
                               {"coordinator_port": PORTS["coordinator"]})
    wait_up(PORTS["authority"])
    witness_ports = [PORTS[w] for w in ("W1", "W2", "W3")]
    procs["ledger"] = start("ledger", S.run_ledger, PORTS["ledger"], witness_ports)
    wait_up(PORTS["ledger"])
    for w in ("W1", "W2", "W3"):
        procs[w] = start(w, S.run_witness, PORTS[w], w, PORTS["ledger"])
        wait_up(PORTS[w])
    procs["coordinator"] = start("coordinator", S.run_coordinator, PORTS["coordinator"], PORTS["authority"],
                                 PORTS["ledger"])
    wait_up(PORTS["coordinator"])
    procs["relay"] = start("relay", S.run_relay, PORTS["relay"],
                           {k: v for k, v in PORTS.items() if k in ("coordinator", "gateway", "B1", "B2", "R1", "C1", "C2", "A1")})
    wait_up(PORTS["relay"])
    owners = {"B1": "m_alice", "B2": "m_bob", "C1": "m_carol", "C2": "m_carol", "A1": "m_thox_audit"}
    for nid, stage in (("B1", "s1"), ("B2", "s1"), ("C1", "s2"), ("C2", "s2"), ("A1", "s1")):
        say(f"starting stage node {nid}")
        procs[nid] = start(nid, S.run_stage_node, PORTS[nid], nid, stage, "auditor" if nid == "A1" else "contributor",
                           BEARER[owners[nid]], PORTS["authority"], PORTS["coordinator"])
        wait_up(PORTS[nid], 240)
    say("starting cloud gateway")
    procs["gateway"] = start("gateway", S.run_gateway, PORTS["gateway"], PORTS["authority"])
    wait_up(PORTS["gateway"], 240)
    dev = Device()
    sc = ev["scenarios"]

    # ------------------------------------------------ A. enrolment and pool
    say("A. enrolment, signed advertisements, refused advertisements")
    status = {n: post(PORTS[n], "/status", {})[1] for n in ("B1", "B2", "C1", "C2", "A1")}
    rogue = Signer()
    ad = {"node_id": "X9", "stage": "s1", "role": "contributor", "port": 1, "hpke_pub": Sealer().pub,
          "model_fp": MODEL_FP, "models": [MODEL], "owner_active": False, "ts": time.time()}
    cert = {"member": "m_mallory", "node_id": "X9", "sign_pub": rogue.pub, "model_fp": MODEL_FP}
    forged = post(PORTS["coordinator"], "/advertise", {"ad": ad, "sig": rogue.sign(ad), "cert": cert,
                                                       "cert_sig": rogue.sign(cert)})
    nonsub = post(PORTS["authority"], "/enrol", {"bearer": BEARER["m_mallory"], "node_id": "X9", "sign_pub": rogue.pub})
    cloud_tag = post(PORTS["B2"], "/admin", {"models": [MODEL, "qwen3-coder:cloud"]})[1]
    restore = post(PORTS["B2"], "/admin", {})[1]
    pool = post(PORTS["coordinator"], "/pool", {})[1]
    sc["A_enrolment"] = {
        "nodes": {n: {k: s[k] for k in ("stage", "role", "cert_ok", "first_advert_code", "params_held", "params_total", "pid")}
                  for n, s in status.items()},
        "distinct_pids": len({s["pid"] for s in status.values()} | {os.getpid()}),
        "forged_certificate_advert": {"code": forged[0], **forged[1]},
        "non_subscriber_enrol": {"code": nonsub[0], **nonsub[1]},
        "cloud_model_tag_advert": {"code": cloud_tag["advertise_code"], **cloud_tag["advertise"]},
        "restored_advert_code": restore["advertise_code"],
        "pool_size": len(pool["nodes"]),
        "pass": all(s["cert_ok"] and s["first_advert_code"] == 200 for s in status.values()) and forged[0] == 403
                and nonsub[0] == 403 and cloud_tag["advertise_code"] == 422 and restore["advertise_code"] == 200,
    }

    # ------------------------------------------------ B. tokens
    say("B. blind tokens: issue, redeem, double spend, forgery, audience, budget")
    code_ok, toks = dev.get_tokens("m_dana", "base", 3, "community")
    code_ns, out_ns = dev.get_tokens("m_mallory", "base", 1, "community")
    code_bud, out_bud = dev.get_tokens("m_erin", "base", S.BASE_BUDGET + 1, "community")
    code_contrib0, _ = dev.get_tokens("m_dana", "contrib", 1, "community")
    first = dev.coordinator({"op": "lease", "token": toks[0]})
    again = dev.coordinator({"op": "lease", "token": toks[0]})
    forged_tok = dict(toks[1], sig=b64(os.urandom(256)))
    forged_res = dev.coordinator({"op": "lease", "token": forged_tok})
    _, cloud_toks = dev.get_tokens("m_dana", "base", 1, "cloud")
    wrong_aud = dev.coordinator({"op": "lease", "token": cloud_toks[0]})
    local_only = dev.coordinator({"op": "lease", "token": toks[1], "privacy_class": "local_only"})
    mesh_only = dev.coordinator({"op": "lease", "token": toks[1], "privacy_class": "mesh_only"})
    confidential = dev.coordinator({"op": "lease", "token": toks[1], "privacy_class": "confidential"})
    dev.coordinator({"op": "close", "lease_id": first["lease"]["lease_id"], "receipts": []})
    sc["B_tokens"] = {
        "issue_subscriber_code": code_ok, "issue_non_subscriber": {"code": code_ns, **out_ns},
        "issue_over_budget": {"code": code_bud, "error": out_bud.get("error")},
        "issue_contrib_tier_without_credit_code": code_contrib0,
        "redeem_first": "lease" in first, "redeem_again": again.get("error"), "forged_signature": forged_res.get("error"),
        "wrong_audience": wrong_aud.get("error"), "local_only_class": local_only.get("error"),
        "mesh_only_class": mesh_only.get("error"), "confidential_class": confidential.get("error"),
        "plan_digest_in_lease": bool(first["lease"].get("plan_digest")),
        "lease_signature_valid": verify(dev.coord["sign_pub"], first["lease"], first["sig"]),
        "pass": code_ok == 200 and code_ns == 403 and code_bud == 429 and code_contrib0 == 429 and "lease" in first
                and again.get("error") == "double_spend" and forged_res.get("error") == "invalid_token"
                and wrong_aud.get("error") == "invalid_token"
                and local_only.get("error") == "local_only_never_leaves_device"
                and mesh_only.get("error") == "mesh_only_never_leaves_owner_devices"
                and confidential.get("error") == "confidential_unavailable_no_attested_boundary",
    }
    dev.auditor_pub = next(n["hpke_pub"] for n in post(PORTS["coordinator"], "/pool", {})[1]["nodes"]
                           if n["role"] == "auditor")

    # ------------------------------------------------ C. community inference
    say("C. community-plane inference, token-exact against the whole model, every hop of one request audited")
    rows = []
    for i, prompt in enumerate(PROMPTS):
        base = dev.whole(prompt)
        lease = dev.lease("m_dana")
        r = dev.community_generate(prompt, lease, audit_q=1.0 if i == 0 else 0.0, rng=random.Random(1))
        rows.append({"prompt": prompt, "token_exact": r.get("tokens") == base, "seconds": r.get("seconds"),
                     "hop_ms_median": r.get("hop_ms_median"), "receipts": r.get("receipts"),
                     "route": r.get("final_route"), "credited": r.get("closed", {}).get("credited"),
                     "audited_steps": len(r.get("audits", [])),
                     "audit_all_match": all(all(a["match"]) for a in r.get("audits", [])), "text": r.get("text")})
        say(f"   prompt {i + 1}/{len(PROMPTS)} token_exact={rows[-1]['token_exact']} {r.get('seconds', 0):.1f}s")
    ledger = post(PORTS["authority"], "/ledger", {})[1]
    sc["C_inference"] = {
        "requests": len(rows), "new_tokens_each": S.MAX_NEW_TOKENS,
        "token_exact": sum(r["token_exact"] for r in rows),
        "receipts_verified": sum(r["receipts"] or 0 for r in rows),
        "honest_audited_steps": rows[0]["audited_steps"], "honest_audit_all_match": rows[0]["audit_all_match"],
        "seconds_per_request_median": statistics.median(r["seconds"] for r in rows),
        "hop_ms_median": statistics.median(r["hop_ms_median"] for r in rows),
        "credits_after": ledger["credits"], "budgets_after": ledger["budgets"], "rows": rows,
        "pass": all(r["token_exact"] for r in rows) and rows[0]["audit_all_match"] and rows[0]["audited_steps"] == S.MAX_NEW_TOKENS,
    }

    # ------------------------------------------------ D. owner protection
    say("D. owner returns mid-request: device drains, request moves to the standby contributor")
    base = dev.whole(PROMPTS[1])
    lease = dev.lease("m_dana")
    first_route = [x["node_id"] for x in lease["lease"]["route"]]

    def owner_back(step):
        if step == 8 and not owner_back.done:
            owner_back.done = True
            post(PORTS[first_route[0]], "/admin", {"owner_active": True})
    owner_back.done = False
    r = dev.community_generate(PROMPTS[1], lease, on_step=owner_back)
    pool_during = {n["node_id"]: n["owner_active"] for n in post(PORTS["coordinator"], "/pool", {})[1]["nodes"]}
    lease2 = dev.lease("m_dana")
    route_while_active = [x["node_id"] for x in lease2["lease"]["route"]]
    dev.coordinator({"op": "close", "lease_id": lease2["lease"]["lease_id"], "receipts": []})
    post(PORTS[first_route[0]], "/admin", {"owner_active": False})
    pool_after = {n["node_id"]: n["owner_active"] for n in post(PORTS["coordinator"], "/pool", {})[1]["nodes"]}
    sc["D_owner_protection"] = {
        "first_route": first_route, "events": r.get("events"), "final_route": r.get("final_route"),
        "token_exact": r.get("tokens") == base, "pool_owner_active_during": pool_during,
        "new_lease_route_while_owner_active": route_while_active, "pool_owner_active_after": pool_after,
        "pass": r.get("tokens") == base and first_route[0] not in (r.get("final_route") or first_route)
                and first_route[0] not in route_while_active and not pool_after[first_route[0]],
    }

    # ------------------------------------------------ E. contributor dies
    say("E. a contributor process is killed mid-request: hop fails closed with attribution, request fails over")
    base = dev.whole(PROMPTS[2])
    lease = dev.lease("m_dana")
    route0 = [x["node_id"] for x in lease["lease"]["route"]]
    victim = route0[1]

    def kill(step):
        if step == 12 and procs[victim].is_alive():
            procs[victim].kill()
            procs[victim].join(5)
    r = dev.community_generate(PROMPTS[2], lease, on_step=kill)
    sc["E_contributor_death"] = {
        "route_before": route0, "killed": victim, "killed_process_alive_after": procs[victim].is_alive(),
        "events": r.get("events"), "final_route": r.get("final_route"), "token_exact": r.get("tokens") == base,
        "pass": r.get("tokens") == base and victim not in (r.get("final_route") or route0)
                and any(e["event"] == "hop_failed" and e["node"] == victim for e in r.get("events", [])),
    }

    # ------------------------------------------------ F. audits against a cheating contributor
    say("F. cheating contributor: audit-only detection for three cheats, then slashing and reroute")
    cheater = "B1"
    detect = {}
    for cheat in ("noise", "fp16", "skip1"):
        post(PORTS[cheater], "/admin", {"cheat": cheat})
        base = dev.whole(PROMPTS[3])
        lease = dev.lease("m_dana")
        plain = dev.community_generate(PROMPTS[3], lease)                      # no audit: does the output even change?
        lease = dev.lease("m_dana")
        r = dev.community_generate(PROMPTS[3], lease, audit_q=1.0, rng=random.Random(2), submit_fraud=False)
        if r.get("lease"):
            dev.coordinator({"op": "close", "lease_id": r["lease"]["lease"]["lease_id"], "receipts": []})
        div = next((i for i, (x, y) in enumerate(zip(plain.get("tokens", []), base)) if x != y), None)
        detect[cheat] = {"digest_audit_detected_at_step": r.get("detected_at_step"),
                         "unaudited_output_token_exact": plain.get("tokens") == base, "first_token_divergence": div}
    # now the full penalty path with a sampled audit, cheat still skip1
    trials = []
    base = dev.whole(PROMPTS[4])
    lease = dev.lease("m_dana")
    r = dev.community_generate(PROMPTS[4], lease, audit_q=0.25, rng=random.Random(20261110))
    ledger = post(PORTS["authority"], "/ledger", {})[1]
    pool = {n["node_id"]: n["suspended"] for n in post(PORTS["coordinator"], "/pool", {})[1]["nodes"]}
    after = dev.lease("m_dana")
    route_after = [x["node_id"] for x in after["lease"]["route"]]
    dev.coordinator({"op": "close", "lease_id": after["lease"]["lease_id"], "receipts": []})
    sc["F_audit"] = {
        "cheater": cheater, "audit_only": detect, "sampled_audit_rate": 0.25, "events": r.get("events"),
        "audits": r.get("audits"), "final_route": r.get("final_route"),
        "detected_at_step": next((e["step"] for e in r.get("events", []) if e["event"] == "audit_mismatch"), None),
        "output_token_exact_after_restart": r.get("tokens") == base,
        "suspended": pool, "credits_after_slash": ledger["credits"], "route_after_suspension": route_after,
        "pass": all(d["digest_audit_detected_at_step"] == 0 for d in detect.values()) and pool.get(cheater) is True
                and ledger["credits"].get("m_alice") is not None and cheater not in route_after and r.get("tokens") == base
                and any(e["event"] == "fraud_proof" and e["accepted"] for e in r.get("events", [])),
    }
    post(PORTS[cheater], "/admin", {"cheat": None})

    # ------------------------------------------------ K. a contributor joins mid-run with a whole remote replica
    say("K. replica route against pipeline route: a device joins mid-run holding both remote ranges")
    procs["R1"] = start("R1", S.run_stage_node, PORTS["R1"], "R1", "s12", "contributor", BEARER["m_bob"],
                        PORTS["authority"], PORTS["coordinator"])
    wait_up(PORTS["R1"], 240)
    r1_status = post(PORTS["R1"], "/status", {})[1]
    trials = []
    n_trials, n_tok = 30, 8
    for topo in ("pipeline", "replica"):                                 # one labelled warm-up each, kept
        lease = dev.lease("m_dana", topology=topo)
        w = dev.community_generate(PROMPTS[0], lease, n_tokens=n_tok)
        trials.append({"topology": topo, "warmup": True, "hop_ms_mean": w["hop_ms_mean"], "token_exact": w["tokens"] == dev.whole(PROMPTS[0], n_tok)})
    order = [("pipeline", "replica")[(i + (i // 2)) % 2] for i in range(2 * n_trials)]   # ABBA blocks
    for i, topo in enumerate(order):
        prompt = PROMPTS[i % len(PROMPTS)]
        lease = dev.lease("m_dana", topology=topo)
        r = dev.community_generate(prompt, lease, n_tokens=n_tok, audit_q=1.0 if i < 2 else 0.0, rng=random.Random(i))
        trials.append({"topology": topo, "warmup": False, "trial": i, "hop_ms_mean": r["hop_ms_mean"],
                       "hop_ms_first": r["hop_ms_first"], "seconds": r["seconds"], "route": r["final_route"],
                       "receipts": r["receipts"], "token_exact": r["tokens"] == dev.whole(prompt, n_tok),
                       "audit_all_match": all(all(a["match"]) for a in r["audits"])})

    def stats(topo):
        xs = [t["hop_ms_mean"] for t in trials if t["topology"] == topo and not t["warmup"]]
        mean = statistics.fmean(xs)
        cv = statistics.stdev(xs) / mean * 100
        rng_ = random.Random(7)
        boots = sorted(statistics.fmean(rng_.choices(xs, k=len(xs))) for _ in range(2000))
        return {"trials": len(xs), "mean_ms": mean, "ci95_ms": [boots[49], boots[1949]], "cv_percent": cv,
                "d37_dispersion_condition": cv <= 10.0}
    kp, kr = stats("pipeline"), stats("replica")
    measured = [t for t in trials if not t["warmup"]]
    sc["K_replica_vs_pipeline"] = {
        "joined_mid_run": {k_: r1_status[k_] for k_ in ("stage", "cert_ok", "first_advert_code", "params_held")},
        "tokens_per_trial": n_tok, "pipeline": kp, "replica": kr,
        "replica_over_pipeline": kr["mean_ms"] / kp["mean_ms"],
        "all_token_exact": all(t["token_exact"] for t in trials), "attempts": len(trials), "completed": len(trials),
        "replica_receipts_per_step": 1, "pipeline_receipts_per_step": 2,
        "replica_audit_all_match": all(t["audit_all_match"] for t in measured if t["topology"] == "replica"),
        "trials": trials,
        "pass": all(t["token_exact"] for t in trials) and r1_status["first_advert_code"] == 200
                and all(t["route"] == ["R1"] for t in measured if t["topology"] == "replica"),
    }

    # ------------------------------------------------ G. tier-weighted admission and issuance budgets
    say("G. contribution raises the issuance budget; admission interleaves tiers 3:1")
    ledger = post(PORTS["authority"], "/ledger", {})[1]
    bob_budget = ledger["budgets"]["m_carol"]["contrib"]
    n_contrib = min(4, bob_budget)
    _, ctoks = dev.get_tokens("m_carol", "contrib", n_contrib, "community")
    _, btoks = dev.get_tokens("m_erin", "base", 8, "community")
    tickets = []
    for t in btoks + ctoks:
        tickets.append((t["tier"], dev.coordinator({"op": "lease", "token": t, "hold": True})["queued"]))
    order, waiting = [], dict((tk, tier) for tier, tk in tickets)
    while waiting:
        for tk in list(waiting):
            got = dev.coordinator({"op": "poll", "ticket": tk})
            if "lease" in got:
                order.append(waiting.pop(tk))
                dev.coordinator({"op": "close", "lease_id": got["lease"]["lease_id"], "receipts": []})
    over = dev.get_tokens("m_erin", "base", S.BASE_BUDGET, "community")
    sc["G_admission"] = {
        "contributor_contrib_budget": bob_budget, "consumer_contrib_budget": ledger["budgets"]["m_dana"]["contrib"],
        "submitted": {"base": len(btoks), "contrib": n_contrib}, "tier_weight": S.TIER_WEIGHT, "grant_order": order,
        "contrib_grants_in_first_half": order[:len(order) // 2].count("contrib"),
        "heavy_member_over_budget": {"code": over[0], "error": over[1].get("error") if isinstance(over[1], dict) else None},
        "pass": bob_budget > 0 and ledger["budgets"]["m_dana"]["contrib"] == 0 and over[0] == 429
                and order[:len(order) // 2].count("contrib") >= n_contrib - 1 and len(order) == len(tickets),
    }

    # ------------------------------------------------ L. load-indexed issuance
    say("L. load-indexed issuance: past the budget, a token is issued only while the pool reports idle capacity")
    used = post(PORTS["authority"], "/ledger", {})[1]["issued"].get("m_erin", {}).get("base", 0)
    dev.get_tokens("m_erin", "base", S.BASE_BUDGET - used, "community")          # spend the whole budget
    idle_before = post(PORTS["coordinator"], "/load", {})[1]
    code_idle, out_idle = post(PORTS["authority"], "/issue", {"bearer": BEARER["m_erin"], "tier": "base", "blinded": ["12345"]})
    busy_a = dev.lease("m_dana", topology="pipeline")
    busy_b = dev.lease("m_dana", topology="replica")
    busy_load = post(PORTS["coordinator"], "/load", {})[1]
    code_busy, out_busy = post(PORTS["authority"], "/issue", {"bearer": BEARER["m_erin"], "tier": "base", "blinded": ["12345"]})
    for x in (busy_a, busy_b):
        dev.coordinator({"op": "close", "lease_id": x["lease"]["lease_id"], "receipts": []})
    code_after, out_after = post(PORTS["authority"], "/issue", {"bearer": BEARER["m_erin"], "tier": "base", "blinded": ["12345"]})
    code_contrib, _ = post(PORTS["authority"], "/issue", {"bearer": BEARER["m_erin"], "tier": "contrib", "blinded": ["12345"]})
    sc["L_load_indexed_issuance"] = {
        "pool_idle_before": idle_before.get("idle"), "over_budget_while_idle": {"code": code_idle, "surplus": out_idle.get("surplus")},
        "pool_idle_while_all_routes_leased": busy_load.get("idle"),
        "over_budget_while_busy": {"code": code_busy, "error": out_busy.get("error")},
        "over_budget_after_release": {"code": code_after, "surplus": out_after.get("surplus")},
        "contributor_tier_never_issued_as_surplus_code": code_contrib,
        "surplus_issued": post(PORTS["authority"], "/ledger", {})[1]["surplus_issued"],
        "pass": idle_before.get("idle") is True and code_idle == 200 and out_idle.get("surplus") is True
                and busy_load.get("idle") is False and code_busy == 429 and code_after == 200 and code_contrib == 429,
    }

    # ------------------------------------------------ H. cloud plane
    say("H. cloud plane through the relay, labelled, refused for community-class requests")
    prompt = f"Repeat this phrase once: {CANARY}"
    base = dev.whole(prompt)
    _, ct = dev.get_tokens("m_dana", "base", 2, "cloud")
    t0 = time.perf_counter()
    _, res = dev.sealed("gateway", dev.gateway["hpke_pub"], {"token": ct[0], "prompt": prompt, "privacy_class": "cloud"})
    cloud_s = time.perf_counter() - t0
    _, replay = dev.sealed("gateway", dev.gateway["hpke_pub"], {"token": ct[0], "prompt": prompt, "privacy_class": "cloud"})
    _, refused = dev.sealed("gateway", dev.gateway["hpke_pub"], {"token": ct[1], "prompt": prompt, "privacy_class": "community"})
    sc["H_cloud_plane"] = {
        "plane_label": res.get("plane"), "notice": res.get("notice"), "tokens_match_local_whole_model": res.get("tokens") == base,
        "seconds": cloud_s, "token_replay": replay.get("error"), "community_class_at_cloud": refused.get("error"),
        "pass": res.get("plane") == "cloud" and res.get("tokens") == base and replay.get("error") == "double_spend"
                and refused.get("error") == "privacy_class_forbids_cloud_plane",
    }

    # ------------------------------------------------ J. settlement ledger
    say("J. settlement ledger: seal an epoch, witness cosignatures, inclusion proof, replay, fork attempt")
    code, sealed_head = post(PORTS["ledger"], "/seal_epoch", {})
    linfo = post(PORTS["ledger"], "/info", {})[1]
    head = sealed_head["head"]
    cos_ok = sum(verify(c["sign_pub"], head, c["sig"]) for c in sealed_head["cosignatures"])
    rp = post(PORTS["ledger"], "/replay", {})[1]
    entries = [unb64(e) for e in rp["entries"]]
    credits: dict[str, float] = {}
    sig_ok = 0
    for e in entries:
        obj = json.loads(e)
        sig_ok += verify(dev.coord["sign_pub"], obj["record"], obj["sig"])
        rec = obj["record"]
        if rec["kind"] == "service":
            credits[rec["member"]] = credits.get(rec["member"], 0.0) + rec["tokens"]
        else:
            credits[rec["member"]] = 0.0
    auth = post(PORTS["authority"], "/ledger", {})[1]["credits"]
    slash_seq = next(i for i, e in enumerate(entries) if json.loads(e)["record"]["kind"] == "slash")
    pr = post(PORTS["ledger"], "/proof", {"seq": slash_seq})[1]
    incl = merkle_verify(unb64(pr["entry"]), pr["path"], head["root"])
    tampered = unb64(pr["entry"]).replace(b'"slash"', b'"slasH"')
    incl_tampered = merkle_verify(tampered, pr["path"], head["root"])
    fork = post(PORTS["ledger"], "/_lab_equivocate", {})[1]
    code2, head2 = post(PORTS["ledger"], "/seal_epoch", {})
    text = b"\n".join(entries)
    sc["J_ledger"] = {
        "entries": len(entries), "entry_signatures_valid": sig_ok, "epoch": head["epoch"], "root": head["root"],
        "ledger_head_signature_valid": verify(linfo["sign_pub"], head, sealed_head["sig"]),
        "witness_cosignatures_valid": cos_ok, "witnesses": 3,
        "seal_build_ms": sealed_head["build_ms"], "seal_cosign_ms": sealed_head["cosign_ms"],
        "replayed_credits": credits, "authority_credits": auth, "replay_matches_authority": credits == auth,
        "slash_entry_seq": slash_seq, "inclusion_proof_hashes": len(pr["path"]), "inclusion_proof_valid": incl,
        "tampered_entry_proof_valid": incl_tampered,
        "fork_attempt": {"cosigned_by": fork["cosigned_by"], "refusals": [r_.get("error") for r_ in fork["refused"]]},
        "next_epoch_chains": code2 == 200 and head2["head"]["prev"] == sha(canon(head)),
        "ledger_contains_consumer_account": any(BEARER[m].encode() in text or m.encode() in text for m in ("m_dana", "m_erin")),
        "ledger_contains_prompt": any(p_.encode() in text for p_ in PROMPTS + [CANARY]),
        "pass": code == 200 and cos_ok == 3 and sig_ok == len(entries) and credits == auth and incl and not incl_tampered
                and fork["cosigned_by"] == 0 and code2 == 200 and head2["head"]["prev"] == sha(canon(head)),
    }

    # ------------------------------------------------ I. information flow
    say("I. information-flow scan over everything each process received")
    groups = {"consumer_account": [b64(BEARER[m].encode()) for m in ("m_dana", "m_erin")],
              "token_value": [b64(b64(m).encode()) for m in dev.token_msgs] + [b64(m) for m in dev.token_msgs],
              "prompt_text": [b64(CANARY.encode())] + [b64(p.encode()) for p in PROMPTS]}
    matrix = {}
    for name in ("authority", "coordinator", "relay", "B1", "B2", "R1", "C2", "A1", "gateway"):
        _, c = post(PORTS[name], "/_scan", {"groups": groups}, timeout=300.0)
        matrix[name] = {"inbound_messages": c["inbound_messages"], "inbound_bytes": c["inbound_bytes"],
                        "saw_consumer_account": c["found"]["consumer_account"],
                        "saw_token_value": c["found"]["token_value"], "saw_prompt_text": c["found"]["prompt_text"]}
        (OUT / f"events_{name}.json").write_text(json.dumps(post(PORTS[name], "/_capture", {})[1]["events"], indent=1))
    expect = {"authority": (True, False, False), "coordinator": (False, False, False), "relay": (False, False, False),
              "B1": (False, False, False), "B2": (False, False, False), "R1": (False, False, False), "C2": (False, False, False),
              "A1": (False, False, False), "gateway": (False, False, False)}
    sc["I_information_flow"] = {
        "method": "each process records every request body it receives; the lab then searches those bytes for "
                  "consumer account bearers, redeemed token values and prompt text. Sealed bodies are opaque to "
                  "this scan by construction, so the scan shows what a party could read off the wire, not what it "
                  "decrypts: the coordinator and gateway decrypt tokens, stage nodes decrypt activations, and the "
                  "gateway decrypts the prompt.",
        "wire_matrix": matrix,
        "decrypts_by_design": {"coordinator": ["token"], "gateway": ["token", "prompt"],
                               "stage nodes and auditor": ["activations, which prior work shows can be inverted to text"],
                               "authority": ["account, blinded token only"], "relay": []},
        "tokens_issued": len(dev.token_msgs), "relay_ciphertext_bytes": dev.relay_bytes,
        "pass": all((m["saw_consumer_account"], m["saw_token_value"], m["saw_prompt_text"]) == expect[n]
                    for n, m in matrix.items()),
    }

    ev["summary"] = {k: v["pass"] for k, v in sc.items()}
    ev["all_pass"] = all(ev["summary"].values())
    ev["processes"] = {k: p.pid for k, p in procs.items()}
    ev["rss_mb"] = {k: rss_mb(p.pid) for k, p in procs.items() if p.is_alive()}
    body = json.dumps(ev, indent=1)
    (OUT / "evidence.json").write_text(body)
    say(f"summary {ev['summary']}")
    say(f"evidence sha256 {hashlib.sha256(body.encode()).hexdigest()}")
    (OUT / "transcript.log").write_text("\n".join(LOG) + "\n")
    for p in procs.values():
        if p.is_alive():
            p.terminate()
    return 0 if ev["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
