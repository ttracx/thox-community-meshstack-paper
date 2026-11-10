"""The parties of the community mesh, each run as its own process.

  authority   subscription authority: accounts, device certificates, blind token
              issuance with per-epoch budgets, contribution credits, slashing
  coordinator pool membership, token redemption, leases, tier-weighted admission
  relay       forwards sealed envelopes it cannot open; hides who is asking
  stage node  a contributor device holding a contiguous layer range of the model
  auditor     replays sampled hops and signs fraud proofs
  gateway     the cloud plane: a hosted whole model behind the relay (stand-in)

Trust boundaries are enforced by what each process is given: the relay holds
no decryption key, the authority never receives a token, and the coordinator
and stage nodes never receive an account identifier.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time

from .common import (MODEL, MODEL_FP, REVISION, STAGES, BlindKey, Capture, Sealer, Signer, b64, canon, leaf_hash,
                     merkle_levels, merkle_proof, post, seal, serve, sha, token_verify, unb64, verify)

LEASE_TTL_S = 120.0
TIER_WEIGHT = {"base": 1, "contrib": 3}
BASE_BUDGET = 120        # tokens per epoch for any subscriber
BONUS_PER_100 = 2        # contrib-tier tokens per 100 token-steps of verified service given
MAX_NEW_TOKENS = 32      # one token authorises one request of at most this many generated tokens


# ------------------------------------------------------------- authority ----
def run_authority(port: int, accounts: dict[str, dict], shared: dict):
    """accounts: bearer -> {member, subscriber: bool}."""
    cap = Capture()
    signer = Signer()
    keys = {"base": BlindKey(), "contrib": BlindKey()}
    issued: dict[str, dict[str, int]] = {}
    credits: dict[str, float] = {}
    suspended: set[str] = set()
    surplus_issued: dict[str, int] = {}
    coordinator_pub = {"k": None}
    lock = threading.Lock()

    def info(_r):
        return 200, {"sign_pub": signer.pub, "keys": {t: {"n": str(k.n), "e": k.e} for t, k in keys.items()}}

    def trust(r):  # lab bootstrap: pin the coordinator's key once
        if coordinator_pub["k"] is None:
            coordinator_pub["k"] = r["coordinator_pub"]
        return 200, {"ok": True}

    def enrol(r):
        acct = accounts.get(r.get("bearer", ""))
        if not acct or not acct["subscriber"]:
            return 403, {"error": "not_a_subscriber"}
        cert = {"member": acct["member"], "node_id": r["node_id"], "sign_pub": r["sign_pub"], "model_fp": MODEL_FP}
        cap.log(event="device_enrolled", member=acct["member"], node=r["node_id"])
        return 200, {"cert": cert, "sig": signer.sign(cert)}

    def budget_of(member: str) -> dict[str, int]:
        bonus = int(credits.get(member, 0.0) / 100.0 * BONUS_PER_100)
        return {"base": BASE_BUDGET, "contrib": bonus}

    def issue(r):
        acct = accounts.get(r.get("bearer", ""))
        if not acct or not acct["subscriber"]:
            cap.log(event="issue_refused", reason="not_a_subscriber")
            return 403, {"error": "not_a_subscriber"}
        tier, member = r["tier"], acct["member"]
        with lock:
            used = issued.setdefault(member, {"base": 0, "contrib": 0})
            surplus = False
            if used[tier] + len(r["blinded"]) > budget_of(member)[tier]:
                # Load-indexed issuance: past the budget, a base-tier token is issued only while the pool
                # reports idle capacity. The report is one aggregate bit; it identifies nobody.
                idle = False
                if tier == "base" and len(r["blinded"]) == 1 and shared.get("coordinator_port"):
                    idle = post(shared["coordinator_port"], "/load", {}, timeout=5.0)[1].get("idle", False)
                if not idle:
                    cap.log(event="issue_refused", reason="budget_exhausted", member=member, tier=tier)
                    return 429, {"error": "budget_exhausted", "budget": budget_of(member), "used": dict(used)}
                surplus = True
                surplus_issued[member] = surplus_issued.get(member, 0) + 1
            used[tier] += len(r["blinded"])
        cap.log(event="issued", member=member, tier=tier, count=len(r["blinded"]), surplus=surplus)
        return 200, {"blind_sigs": [str(keys[tier].blind_sign(int(z))) for z in r["blinded"]], "surplus": surplus}

    def credit(r):
        rec = r["record"]
        if not verify(coordinator_pub["k"] or "", rec, r["sig"]):
            return 403, {"error": "bad_signature"}
        with lock:
            if rec["kind"] == "service":
                credits[rec["member"]] = credits.get(rec["member"], 0.0) + rec["tokens"]
            elif rec["kind"] == "slash":
                credits[rec["member"]] = 0.0
                suspended.add(rec["node_id"])
        cap.log(event="ledger", **rec)
        return 200, {"credits": dict(credits), "suspended": sorted(suspended)}

    def ledger(_r):
        return 200, {"credits": dict(credits), "issued": dict(issued), "suspended": sorted(suspended),
                     "surplus_issued": dict(surplus_issued),
                     "budgets": {m: budget_of(m) for m in {a["member"] for a in accounts.values()}}}

    serve(port, {"/info": info, "/trust": trust, "/enrol": enrol, "/issue": issue, "/credit": credit,
                 "/ledger": ledger}, cap)


# ----------------------------------------------------------- coordinator ----
def run_coordinator(port: int, authority_port: int, ledger_port: int):
    cap = Capture()
    signer, sealer = Signer(), Sealer()
    _, ainfo = post(authority_port, "/info", {})
    akeys = {t: (int(k["n"]), k["e"]) for t, k in ainfo["keys"].items()}
    post(authority_port, "/trust", {"coordinator_pub": signer.pub})
    nodes: dict[str, dict] = {}
    spent: set[str] = set()
    leases: dict[str, dict] = {}
    pending: list[dict] = []
    served_by_tier = {"base": 0.0, "contrib": 0.0}
    grant_log: list[dict] = []
    granted_by_ticket: dict[str, dict] = {}
    lock = threading.Lock()
    post(ledger_port, "/trust", {"coordinator_pub": signer.pub})

    def settle(rec: dict):
        """Every credit and every slash goes to the authority and, identically, to the public ledger."""
        body = {"record": rec, "sig": signer.sign(rec)}
        post(authority_port, "/credit", body)
        post(ledger_port, "/append", body)

    def info(_r):
        return 200, {"sign_pub": signer.pub, "hpke_pub": sealer.pub}

    def advertise(r):
        ad, cert = r["ad"], r["cert"]
        if not verify(ainfo["sign_pub"], cert, r["cert_sig"]):
            cap.log(event="advert_refused", reason="no_authority_certificate", node=ad.get("node_id"))
            return 403, {"error": "no_authority_certificate"}
        if cert["node_id"] != ad["node_id"] or not verify(cert["sign_pub"], ad, r["sig"]):
            cap.log(event="advert_refused", reason="bad_node_signature", node=ad.get("node_id"))
            return 403, {"error": "bad_node_signature"}
        if ad["model_fp"] != MODEL_FP:
            return 409, {"error": "model_fingerprint_mismatch"}
        if any(m.endswith(":cloud") or m.startswith("remote:") for m in ad.get("models", [])):
            cap.log(event="advert_refused", reason="cloud_model_is_not_mesh_compute", node=ad["node_id"])
            return 422, {"error": "cloud_model_is_not_mesh_compute"}
        with lock:
            prev = nodes.get(ad["node_id"], {})
            nodes[ad["node_id"]] = {**ad, "member": cert["member"], "sign_pub": cert["sign_pub"],
                                    "suspended": prev.get("suspended", False), "seen": time.time()}
        cap.log(event="advert_ok", node=ad["node_id"], stage=ad["stage"], owner_active=ad["owner_active"])
        return 200, {"ok": True}

    def eligible(stage: str, exclude: list[str]) -> list[dict]:
        out = [n for n in nodes.values() if n["stage"] == stage and not n["owner_active"] and not n["suspended"]
               and not n.get("suspect")
               and n["node_id"] not in exclude and n["role"] == "contributor"]
        busy = {nid for l in leases.values() if l["expires"] > time.time() and not l["closed"] for nid in l["route_ids"]}
        return sorted([n for n in out if n["node_id"] not in busy], key=lambda n: n["node_id"])

    def route(exclude: list[str], topology: str = "pipeline"):
        """Only complete, eligible plans are returned. An ineligible node is excluded, never priced."""
        if topology == "replica":
            whole = eligible("s12", exclude)
            return (whole[0],) if whole else None
        r1, r2 = eligible("s1", exclude), eligible("s2", exclude)
        return (r1[0], r2[0]) if r1 and r2 else None

    def make_lease(tier: str, exclude: list[str], ticket: str | None = None, topology: str = "pipeline"):
        rt = route(exclude, topology)
        if rt is None:
            return None
        body = {"lease_id": os.urandom(8).hex(), "tier": tier, "expires": time.time() + LEASE_TTL_S,
                "max_new_tokens": MAX_NEW_TOKENS, "model_fp": MODEL_FP,
                "route": [{"node_id": n["node_id"], "port": n["port"], "hpke_pub": n["hpke_pub"],
                           "sign_pub": n["sign_pub"], "stage": n["stage"]} for n in rt]}
        body["topology"] = topology
        body["plan_digest"] = sha(canon(body))   # one digest binds route, keys, model, quantum and expiry
        leases[body["lease_id"]] = {"expires": body["expires"], "closed": False, "tier": tier, "topology": topology,
                                    "route_ids": [n["node_id"] for n in rt]}
        grant_log.append({"t": time.time(), "tier": tier, "lease_id": body["lease_id"], "ticket": ticket})
        return {"lease": body, "sig": signer.sign(body)}

    def pump():
        """Tier-weighted admission: grant the pending tier with the least service per unit weight."""
        while pending:
            tiers = sorted({p["tier"] for p in pending}, key=lambda t: (served_by_tier[t] / TIER_WEIGHT[t], t))
            p = next(x for x in pending if x["tier"] == tiers[0])
            got = make_lease(p["tier"], [], p["ticket"], p.get("topology", "pipeline"))
            if got is None:
                return
            served_by_tier[p["tier"]] += MAX_NEW_TOKENS
            pending.remove(p)
            granted_by_ticket[p["ticket"]] = got

    def sealed(r):
        """All client traffic arrives here sealed and through the relay."""
        m = sealer.open(unb64(r["body"]))
        op = m["op"]
        with lock:
            if op == "lease":
                tok = m["token"]
                msg, sig, tier = unb64(tok["msg"]), unb64(tok["sig"]), tok["tier"]
                if not msg.endswith(b"|aud=community") or not token_verify(*akeys[tier], msg, sig):
                    cap.log(event="token_refused", reason="invalid")
                    out = {"error": "invalid_token"}
                elif sha(msg) in spent:
                    cap.log(event="token_refused", reason="double_spend")
                    out = {"error": "double_spend"}
                elif m.get("privacy_class") == "local_only":
                    cap.log(event="lease_refused", reason="local_only_never_leaves_device")
                    out = {"error": "local_only_never_leaves_device"}
                elif m.get("privacy_class") == "mesh_only":
                    cap.log(event="lease_refused", reason="mesh_only_never_leaves_owner_devices")
                    out = {"error": "mesh_only_never_leaves_owner_devices"}
                elif m.get("privacy_class") == "confidential":
                    # No contributed device in this pool offers an attested execution boundary. A self-asserted
                    # flag cannot authorise confidential processing, so the request is refused before dispatch.
                    cap.log(event="lease_refused", reason="confidential_unavailable")
                    out = {"error": "confidential_unavailable_no_attested_boundary"}
                else:
                    spent.add(sha(msg))
                    ticket = os.urandom(6).hex()
                    entry = {"ticket": ticket, "tier": tier, "topology": m.get("topology", "pipeline")}
                    if not any(x["tier"] == tier for x in pending):
                        act = [served_by_tier[x["tier"]] / TIER_WEIGHT[x["tier"]] for x in pending]
                        if act:  # counter lift: a tier that was idle banks no credit
                            served_by_tier[tier] = max(served_by_tier[tier], min(act) * TIER_WEIGHT[tier])
                    pending.append(entry)
                    if not m.get("hold"):
                        pump()
                    got = granted_by_ticket.get(ticket)
                    cap.log(event="token_redeemed", tier=tier, ticket=ticket, granted=bool(got))
                    if got:
                        out = got
                    elif m.get("hold") or m.get("queue"):
                        out = {"queued": ticket}
                    else:
                        pending.remove(entry)
                        spent.discard(sha(msg))
                        out = {"error": "no_capacity"}
            elif op == "poll":
                pump()
                out = granted_by_ticket.get(m["ticket"]) or {"queued": m["ticket"]}
            elif op == "reroute":
                l = leases.get(m["lease_id"])
                if not l or l["closed"] or l["expires"] < time.time():
                    out = {"error": "lease_invalid"}
                else:
                    l["closed"] = True
                    for nid in m.get("exclude", []):      # unreachable or refusing: out of the pool until it re-advertises
                        if nid in nodes:
                            nodes[nid]["suspect"] = True
                    got = make_lease(l["tier"], m.get("exclude", []), None, l.get("topology", "pipeline"))
                    cap.log(event="reroute", lease=m["lease_id"], exclude=m.get("exclude", []), ok=bool(got))
                    out = got or {"error": "no_capacity"}
            elif op == "close":
                l = leases.get(m["lease_id"])
                out = {"error": "lease_invalid"}
                if l and not l["closed"]:
                    l["closed"] = True
                    credited = {}
                    for rc in m["receipts"]:
                        n = nodes.get(rc["body"]["node_id"])
                        if n and rc["body"]["lease_id"] in leases and verify(n["sign_pub"], rc["body"], rc["sig"]):
                            credited[n["member"]] = credited.get(n["member"], 0) + 1
                    for member, steps in credited.items():
                        settle({"kind": "service", "member": member, "tokens": steps, "lease_id": m["lease_id"]})
                    cap.log(event="lease_closed", lease=m["lease_id"], credited=credited)
                    out = {"credited": credited}
                    pump()
            elif op == "fraud":
                proof = m["proof"]
                n = nodes.get(proof["receipt"]["body"]["node_id"])
                aud = nodes.get(proof["auditor"])
                ok = (n and aud and aud["role"] == "auditor"
                      and verify(n["sign_pub"], proof["receipt"]["body"], proof["receipt"]["sig"])
                      and verify(aud["sign_pub"], proof["finding"], proof["finding_sig"])
                      and proof["finding"]["in_digest"] == proof["receipt"]["body"]["in_digest"]
                      and proof["finding"]["expected_out_digest"] != proof["receipt"]["body"]["out_digest"])
                if ok:
                    n["suspended"] = True
                    settle({"kind": "slash", "member": n["member"], "node_id": n["node_id"],
                            "lease_id": proof["receipt"]["body"]["lease_id"],
                            "receipt_sha": sha(canon(proof["receipt"])), "finding_sha": sha(canon(proof["finding"]))})
                    cap.log(event="slashed", node=n["node_id"], member=n["member"])
                out = {"accepted": bool(ok)}
            else:
                out = {"error": "unknown_op"}
        return 200, {"body": b64(seal(m["reply_pub"], out))}

    def pool(_r):
        with lock:
            return 200, {"nodes": [{k: n[k] for k in ("node_id", "stage", "role", "owner_active", "suspended", "member", "hpke_pub")}
                                   for n in nodes.values()], "grants": list(grant_log)}

    def load(_r):
        with lock:
            idle = not pending and (route([], "pipeline") is not None or route([], "replica") is not None)
            return 200, {"idle": idle}

    serve(port, {"/info": info, "/advertise": advertise, "/sealed": sealed, "/pool": pool, "/load": load}, cap)


# ----------------------------------------------------------------- relay ----
def run_relay(port: int, targets: dict[str, int]):
    """Forwards opaque bodies. Holds no key. Logs only destination and size."""
    cap = Capture()

    def forward(r):
        dest = targets.get(r["to"])
        if dest is None:
            return 404, {"error": "unknown_destination"}
        cap.log(event="forward", to=r["to"], bytes=len(r["body"]))
        code, out = post(dest, "/sealed", {"body": r["body"]}, timeout=120.0)
        return (502 if code == 0 else code), out

    def add(r):
        targets[r["name"]] = r["port"]
        return 200, {"ok": True}

    serve(port, {"/forward": forward, "/_add": add}, cap)


# ------------------------------------------------------------ stage node ----
def _load_stage(stage_names: list[str]):
    """Load only the layer ranges this node holds, straight from the checkpoint file.

    The node never materialises the embeddings, the output head or any other party's layers.
    """
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open
    from transformers import AutoConfig
    from transformers.models.llama.modeling_llama import LlamaDecoderLayer, LlamaRotaryEmbedding
    torch.set_num_threads(1)
    cfg = AutoConfig.from_pretrained(MODEL, revision=REVISION)
    path = hf_hub_download(MODEL, "model.safetensors", revision=REVISION)
    parts, held, total = {}, 0, 0
    with safe_open(path, "pt") as f:
        keys = list(f.keys())
        for k in keys:
            n = 1
            for d in f.get_slice(k).get_shape():
                n *= d
            total += n
        for name in stage_names:
            lo, hi = STAGES[name]
            layers = []
            for i in range(lo, hi):
                prefix = f"model.layers.{i}."
                layer = LlamaDecoderLayer(cfg, i).eval()
                layer.load_state_dict({k[len(prefix):]: f.get_tensor(k) for k in keys if k.startswith(prefix)}, strict=True)
                layers.append(layer)
            parts[name] = torch.nn.ModuleList(layers)
            held += sum(p.numel() for p in parts[name].parameters())
    rotary = LlamaRotaryEmbedding(config=cfg)
    return torch, parts, rotary, cfg, held, total


def _run_layers(torch, layers, rotary, h):
    seq = h.shape[1]
    pos = torch.arange(seq).unsqueeze(0)
    mask = torch.full((seq, seq), torch.finfo(h.dtype).min).triu(1)[None, None]
    pe = rotary(h, pos)
    with torch.no_grad():
        for layer in layers:
            out = layer(h, attention_mask=mask, position_ids=pos, position_embeddings=pe)
            h = out[0] if isinstance(out, tuple) else out
    return h


def run_stage_node(port: int, node_id: str, stage: str, role: str, bearer: str, authority_port: int,
                   coordinator_port: int, cheat: str | None = None, extra_models: list[str] | None = None):
    import numpy as np
    cap = Capture()
    signer, sealer = Signer(), Sealer()
    stage_names = ["s1", "s2"] if role == "auditor" or stage == "s12" else [stage]
    torch, parts, rotary, _cfg, held, total = _load_stage(stage_names)
    _, cinfo = post(coordinator_port, "/info", {})
    state = {"owner_active": False, "cheat": cheat, "hops": 0}
    code, enrolment = post(authority_port, "/enrol", {"bearer": bearer, "node_id": node_id, "sign_pub": signer.pub})
    cert_ok = code == 200

    def advertise(models=None):
        ad = {"node_id": node_id, "stage": stage, "role": role, "port": port, "hpke_pub": sealer.pub,
              "model_fp": MODEL_FP, "models": models or [MODEL] + (extra_models or []),
              "owner_active": state["owner_active"], "ts": time.time()}
        body = {"ad": ad, "sig": signer.sign(ad), "cert": enrolment.get("cert", {}),
                "cert_sig": enrolment.get("sig", "")}
        return post(coordinator_port, "/advertise", body)

    first = advertise()

    def compute(name: str, h):
        if name == "s12":                      # a whole remote replica: both ranges on one device, one hop
            return compute("s2", compute("s1", h))
        layers = parts[name]
        c = state["cheat"]
        if c == "skip1" and role == "contributor":
            layers = [l for i, l in enumerate(layers) if i != 5]
        out = _run_layers(torch, layers, rotary, h)
        if c == "noise" and role == "contributor":
            out = out + torch.randn(out.shape, generator=torch.Generator().manual_seed(7)) * out.pow(2).mean().sqrt() * 1e-3
        if c == "fp16" and role == "contributor":
            out = out.to(torch.float16).to(torch.float32)
        return out

    def decode(m):
        raw = unb64(m["h"])
        return raw, torch.from_numpy(np.frombuffer(raw, dtype=np.float32).copy()).reshape(m["shape"])

    def sealed(r):
        m = sealer.open(unb64(r["body"]))
        if m["op"] == "hop":
            lease = m["lease"]
            if not verify(cinfo["sign_pub"], lease["lease"], lease["sig"]) or lease["lease"]["expires"] < time.time():
                return 403, {"error": "lease_invalid"}
            if node_id not in [x["node_id"] for x in lease["lease"]["route"]]:
                return 403, {"error": "not_on_route"}
            if state["owner_active"]:
                cap.log(event="hop_refused", reason="owner_active")
                return 409, {"error": "owner_active"}
            if m["step"] >= lease["lease"]["max_new_tokens"]:
                return 403, {"error": "quantum_exceeded"}
            raw, h = decode(m)
            out = compute(stage, h)
            last_only = stage in ("s2", "s12")
            out_t = out[:, -1:, :] if last_only else out
            out_raw = out_t.contiguous().numpy().tobytes()
            body = {"lease_id": lease["lease"]["lease_id"], "plan_digest": lease["lease"].get("plan_digest"),
                    "step": m["step"], "node_id": node_id, "stage": stage,
                    "in_digest": sha(raw), "out_digest": sha(out_raw)}
            receipt = {"body": body, "sig": signer.sign(body)}
            state["hops"] += 1
            cap.log(event="hop", step=m["step"], lease=body["lease_id"])
            receipts = m.get("receipts", []) + [receipt]
            if stage == "s1":
                nxt = [x for x in lease["lease"]["route"] if x["stage"] == "s2"][0]
                fwd = {"op": "hop", "lease": lease, "step": m["step"], "h": b64(out_raw),
                       "shape": list(out_t.shape), "receipts": receipts, "reply_pub": m["reply_pub"]}
                code2, back = post(nxt["port"], "/sealed", {"body": b64(seal(nxt["hpke_pub"], fwd))}, timeout=120.0)
                if code2 != 200:   # fail closed with hop attribution
                    return 502, {"error": "downstream_failed", "hop": nxt["node_id"], "detail": back.get("error")}
                return 200, back
            reply = {"h": b64(out_raw), "shape": list(out_t.shape), "receipts": receipts}
            return 200, {"body": b64(seal(m["reply_pub"], reply))}
        if m["op"] == "audit" and role == "auditor":
            raw, h = decode(m)
            findings, cur, cur_raw = [], h, raw
            for rc in m["receipts"]:
                name = rc["body"]["stage"]
                out = compute(name, cur)
                out_t = out[:, -1:, :] if name in ("s2", "s12") else out
                out_raw = out_t.contiguous().numpy().tobytes()
                finding = {"node_id": rc["body"]["node_id"], "lease_id": rc["body"]["lease_id"],
                           "step": rc["body"]["step"], "in_digest": sha(cur_raw),
                           "claimed_in_digest": rc["body"]["in_digest"],
                           "expected_out_digest": sha(out_raw), "match": sha(out_raw) == rc["body"]["out_digest"]}
                findings.append({"finding": finding, "finding_sig": signer.sign(finding), "auditor": node_id})
                cur, cur_raw = out_t, out_raw
                if not finding["match"]:
                    break
            cap.log(event="audit", results=[f["finding"]["match"] for f in findings])
            return 200, {"body": b64(seal(m["reply_pub"], {"findings": findings}))}
        return 400, {"error": "unknown_op"}

    def admin(r):  # the device owner's local switch; never reachable through the relay
        if "owner_active" in r:
            state["owner_active"] = bool(r["owner_active"])
        if "cheat" in r:
            state["cheat"] = r["cheat"]
        code2, out = advertise(r.get("models"))
        return 200, {"advertise_code": code2, "advertise": out, "owner_active": state["owner_active"]}

    def status(_r):
        return 200, {"node_id": node_id, "stage": stage, "role": role, "cert_ok": cert_ok,
                     "first_advert": first[1], "first_advert_code": first[0], "hops": state["hops"],
                     "params_held": held, "params_total": total, "pid": os.getpid()}

    serve(port, {"/sealed": sealed, "/admin": admin, "/status": status}, cap)


# --------------------------------------------------------- cloud gateway ----
def run_gateway(port: int, authority_port: int):
    """Stand-in for a hosted model provider. It can read the prompt. It cannot tell who sent it."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(1)
    cap = Capture()
    sealer = Sealer()
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, dtype=torch.float32).eval()
    _, ainfo = post(authority_port, "/info", {})
    akeys = {t: (int(k["n"]), k["e"]) for t, k in ainfo["keys"].items()}
    spent: set[str] = set()

    def info(_r):
        return 200, {"hpke_pub": sealer.pub, "plane": "cloud"}

    def sealed(r):
        m = sealer.open(unb64(r["body"]))
        t = m["token"]
        msg = unb64(t["msg"])
        if not msg.endswith(b"|aud=cloud") or not token_verify(*akeys[t["tier"]], msg, unb64(t["sig"])):
            out = {"error": "invalid_token"}
        elif sha(msg) in spent:
            out = {"error": "double_spend"}
        elif m.get("privacy_class") in ("local_only", "mesh_only", "community"):
            out = {"error": "privacy_class_forbids_cloud_plane"}
        else:
            spent.add(sha(msg))
            ids = tok.apply_chat_template([{"role": "user", "content": m["prompt"]}], add_generation_prompt=True,
                                          return_tensors="pt", return_dict=True)
            with torch.no_grad():
                gen = model.generate(**ids, max_new_tokens=MAX_NEW_TOKENS, min_new_tokens=MAX_NEW_TOKENS,
                                     do_sample=False, pad_token_id=tok.eos_token_id)
            new = gen[0, ids["input_ids"].shape[1]:].tolist()
            cap.log(event="cloud_completion", prompt_sha=hashlib.sha256(m["prompt"].encode()).hexdigest()[:16])
            out = {"tokens": new, "text": tok.decode(new), "plane": "cloud",
                   "notice": "served by a hosted provider that can read this prompt"}
        return 200, {"body": b64(seal(m["reply_pub"], out))}

    serve(port, {"/info": info, "/sealed": sealed}, cap)


# ------------------------------------------------------ settlement ledger ----
def run_ledger(port: int, witness_ports: list[int]):
    """Append-only, hash-chained, witness-cosigned log of credits and slashes.

    Off the token path: nothing here is contacted while a request is being served.
    Entries carry contributor member ids, lease ids and digests. They never carry
    a requester identity, a token or a prompt.
    """
    cap = Capture()
    signer = Signer()
    coordinator_pub = {"k": None}
    entries: list[bytes] = []
    heads: list[dict] = []
    sealed_upto = {"n": 0}
    lock = threading.Lock()

    def info(_r):
        return 200, {"sign_pub": signer.pub}

    def trust(r):
        if coordinator_pub["k"] is None:
            coordinator_pub["k"] = r["coordinator_pub"]
        return 200, {"ok": True}

    def append(r):
        if not verify(coordinator_pub["k"] or "", r["record"], r["sig"]):
            return 403, {"error": "bad_signature"}
        with lock:
            entries.append(canon({"seq": len(entries), "record": r["record"], "sig": r["sig"]}))
            return 200, {"seq": len(entries) - 1}

    def make_head(leaves: list[bytes]) -> dict:
        root = merkle_levels([leaf_hash(e) for e in leaves])[-1][0].hex()
        prev = sha(canon(heads[-1]["head"])) if heads else "0" * 64
        return {"epoch": len(heads), "size": len(leaves), "root": root, "prev": prev}

    def cosign(head: dict) -> tuple[list, list]:
        sig = signer.sign(head)
        got, refused = [], []
        for wp in witness_ports:
            code, out = post(wp, "/cosign", {"head": head, "sig": sig})
            (got if code == 200 else refused).append({"port": wp, **out})
        return got, refused

    def seal_epoch(_r):
        with lock:
            t0 = time.perf_counter()
            head = make_head(entries)
            build_ms = (time.perf_counter() - t0) * 1e3
            t1 = time.perf_counter()
            got, refused = cosign(head)
            cosign_ms = (time.perf_counter() - t1) * 1e3
            if len(got) * 2 <= len(witness_ports):
                return 409, {"error": "no_witness_quorum", "refused": refused}
            heads.append({"head": head, "sig": signer.sign(head), "cosignatures": got})
            sealed_upto["n"] = len(entries)
            cap.log(event="epoch_sealed", epoch=head["epoch"], size=head["size"])
            return 200, {**heads[-1], "build_ms": build_ms, "cosign_ms": cosign_ms}

    def proof(r):
        with lock:
            n = heads[-1]["head"]["size"]
            levels = merkle_levels([leaf_hash(e) for e in entries[:n]])
            return 200, {"entry": b64(entries[r["seq"]]), "path": merkle_proof(levels, r["seq"]), "head": heads[-1]}

    def replay(_r):
        with lock:
            return 200, {"entries": [b64(e) for e in entries[:sealed_upto["n"]]], "heads": list(heads)}

    def lab_equivocate(_r):
        """LAB TEST HOOK. Plays a dishonest log operator: re-issue the last epoch with one entry dropped."""
        with lock:
            last = heads[-1]["head"]
            forged_leaves = entries[:last["size"]][1:]
            head = {"epoch": last["epoch"], "size": len(forged_leaves),
                    "root": merkle_levels([leaf_hash(e) for e in forged_leaves])[-1][0].hex(), "prev": last["prev"]}
            got, refused = cosign(head)
            return 200, {"forged_head": head, "cosigned_by": len(got), "refused": refused}

    serve(port, {"/info": info, "/trust": trust, "/append": append, "/seal_epoch": seal_epoch, "/proof": proof,
                 "/replay": replay, "/_lab_equivocate": lab_equivocate}, cap)


def run_witness(port: int, name: str, ledger_port: int):
    """Independent witness: cosigns a head only if it extends the one history this witness has seen."""
    cap = Capture()
    signer = Signer()
    seen: list[dict] = []
    ledger_pub = {"k": None}
    lock = threading.Lock()

    def info(_r):
        return 200, {"name": name, "sign_pub": signer.pub}

    def cosign(r):
        if ledger_pub["k"] is None:
            ledger_pub["k"] = post(ledger_port, "/info", {})[1]["sign_pub"]
        head = r["head"]
        if not verify(ledger_pub["k"], head, r["sig"]):
            return 403, {"error": "bad_ledger_signature", "witness": name}
        with lock:
            prev = sha(canon(seen[-1])) if seen else "0" * 64
            if head["epoch"] != len(seen) or head["prev"] != prev or (seen and head["size"] < seen[-1]["size"]):
                cap.log(event="fork_refused", epoch=head["epoch"])
                return 409, {"error": "fork_detected", "witness": name}
            seen.append(head)
        return 200, {"witness": name, "sign_pub": signer.pub, "sig": signer.sign(head)}

    serve(port, {"/info": info, "/cosign": cosign}, cap)
