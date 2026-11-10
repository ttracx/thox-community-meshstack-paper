"""E4: cost of a blockchain-like settlement ledger kept off the token path.

The ledger is a transparency log, not a consensus chain on the hot path:
per-hop receipts are Ed25519-signed in band (already required for audits);
every epoch the coordinator batches receipts into a SHA-256 Merkle tree
(RFC 9162 hashing: 0x00 leaf prefix, 0x01 node prefix), chains the signed tree
head to the previous one, and W witnesses cosign it. A member checks their own
credit with an inclusion proof against a cosigned head.

Measured here: receipt sign and verify, Merkle root build per batch size,
inclusion proof size and verify time, head cosign and cosign verification.
Medians over RUNS after warm-up. Writes exp/results/ledger.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519

RUNS = 200
BATCHES = [64, 1024, 16384]
WITNESSES = 5


def leaf(b: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + b).digest()


def node(a: bytes, b: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + a + b).digest()


def build(leaves: list[bytes]) -> list[list[bytes]]:
    levels = [leaves]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        levels.append([node(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i] for i in range(0, len(cur), 2)])
    return levels


def proof(levels: list[list[bytes]], idx: int) -> list[tuple[bool, bytes]]:
    out = []
    for lvl in levels[:-1]:
        sib = idx ^ 1
        if sib < len(lvl):
            out.append((sib < idx, lvl[sib]))
        idx //= 2
    return out


def verify_proof(leaf_hash: bytes, path: list[tuple[bool, bytes]], root: bytes) -> bool:
    h = leaf_hash
    for left, sib in path:
        h = node(sib, h) if left else node(h, sib)
    return h == root


def med(xs):
    q = statistics.quantiles(xs, n=4)
    return {"median": statistics.median(xs), "q1": q[0], "q3": q[2]}


def main() -> int:
    sk = ed25519.Ed25519PrivateKey.generate()
    pk = sk.public_key()
    receipt = json.dumps({"lease_id": os.urandom(8).hex(), "step": 17, "node_id": "B1", "stage": "s1",
                          "in_digest": os.urandom(32).hex(), "out_digest": os.urandom(32).hex()}).encode()
    sign_us, verify_us = [], []
    for i in range(RUNS + 20):
        a = time.perf_counter(); sig = sk.sign(receipt)
        b = time.perf_counter(); pk.verify(sig, receipt)
        c = time.perf_counter()
        if i >= 20:
            sign_us.append((b - a) * 1e6); verify_us.append((c - b) * 1e6)
    out = {"host": {"machine": platform.machine(), "python": platform.python_version()}, "runs": RUNS,
           "receipt_bytes": len(receipt), "signature_bytes": len(sig),
           "receipt_sign_us": med(sign_us), "receipt_verify_us": med(verify_us), "batches": []}
    witnesses = [ed25519.Ed25519PrivateKey.generate() for _ in range(WITNESSES)]
    prev = b"\x00" * 32
    for n in BATCHES:
        entries = [receipt + i.to_bytes(4, "big") for i in range(n)]
        reps = 30 if n >= 16384 else RUNS
        build_ms, prove_us, cosign_us, cosign_verify_us = [], [], [], []
        for r in range(reps + 3):
            a = time.perf_counter()
            levels = build([leaf(e) for e in entries])
            root = levels[-1][0]
            b = time.perf_counter()
            path = proof(levels, (r * 7919) % n)
            lf = leaf(entries[(r * 7919) % n])
            c = time.perf_counter()
            ok = verify_proof(lf, path, root)
            d = time.perf_counter()
            head = hashlib.sha256(prev + root + n.to_bytes(8, "big")).digest()
            sigs = [w.sign(head) for w in witnesses]
            e = time.perf_counter()
            for w, s in zip(witnesses, sigs):
                w.public_key().verify(s, head)
            f = time.perf_counter()
            assert ok
            if r >= 3:
                build_ms.append((b - a) * 1e3); prove_us.append((d - c) * 1e6)
                cosign_us.append((e - d) * 1e6); cosign_verify_us.append((f - e) * 1e6)
        prev = head
        out["batches"].append({"receipts": n, "reps": reps, "build_ms": med(build_ms),
                               "build_us_per_receipt": statistics.median(build_ms) * 1e3 / n,
                               "proof_hashes": len(path), "proof_bytes": 32 * len(path),
                               "proof_verify_us": med(prove_us), "witnesses": WITNESSES,
                               "cosign_us": med(cosign_us), "cosign_verify_us": med(cosign_verify_us)})
    Path(__file__).with_name("results").joinpath("ledger.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
