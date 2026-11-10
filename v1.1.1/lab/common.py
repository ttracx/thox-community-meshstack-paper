"""Shared primitives for the THOX community mesh virtual lab.

Everything here is real cryptography and real HTTP on loopback. Nothing is
mocked. The lab is virtual only in the sense that every party is a separate
operating-system process on one host instead of a separate machine.

Primitives:
  - RSA blind signatures, RFC 9474 RSABSSA-SHA384-PSS (subscriber tokens)
  - HPKE base mode, RFC 9180, X25519 / HKDF-SHA256 / ChaCha20-Poly1305 (sealed envelopes)
  - Ed25519, RFC 8032 (advertisements, device certificates, leases, receipts)
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.hazmat.primitives import hashes, hpke, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa, x25519

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
MODEL_FP = hashlib.sha256(f"{MODEL}@{REVISION}".encode()).hexdigest()[:32]
STAGES = {"s0": (0, 10), "s1": (10, 20), "s2": (20, 30)}
SLEN = 48
SUITE = hpke.Suite(hpke.KEM.X25519, hpke.KDF.HKDF_SHA256, hpke.AEAD.CHACHA20_POLY1305)
INFO = b"thox.community.lab.v1"


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def unb64(s: str) -> bytes:
    return base64.b64decode(s)


def canon(obj) -> bytes:
    """Canonical JSON for signing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- Ed25519 ---
class Signer:
    def __init__(self):
        self.sk = ed25519.Ed25519PrivateKey.generate()
        self.pub = b64(self.sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))

    def sign(self, obj) -> str:
        return b64(self.sk.sign(canon(obj)))


def verify(pub_b64: str, obj, sig_b64: str) -> bool:
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(unb64(pub_b64)).verify(unb64(sig_b64), canon(obj))
        return True
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------- HPKE ---
class Sealer:
    def __init__(self):
        self.sk = x25519.X25519PrivateKey.generate()
        self.pub = b64(self.sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))

    def open(self, ct: bytes) -> dict:
        return json.loads(SUITE.decrypt(ct, self.sk, INFO))


def seal(pub_b64: str, obj: dict) -> bytes:
    pk = x25519.X25519PublicKey.from_public_bytes(unb64(pub_b64))
    return SUITE.encrypt(canon(obj), pk, INFO)


# ------------------------------------------------- RFC 9474 blind RSA -------
def _mgf1(seed: bytes, length: int) -> bytes:
    out, counter = b"", 0
    while len(out) < length:
        out += hashlib.sha384(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:length]


def _emsa_pss(msg: bytes, em_bits: int, salt: bytes) -> bytes:
    m_hash = hashlib.sha384(msg).digest()
    em_len = math.ceil(em_bits / 8)
    h = hashlib.sha384(b"\x00" * 8 + m_hash + salt).digest()
    db = b"\x00" * (em_len - len(salt) - len(m_hash) - 2) + b"\x01" + salt
    masked = bytearray(a ^ b for a, b in zip(db, _mgf1(h, em_len - len(m_hash) - 1)))
    masked[0] &= 0xFF >> (8 * em_len - em_bits)
    return bytes(masked) + h + b"\xbc"


def blind(n: int, e: int, msg: bytes) -> tuple[int, int]:
    m = int.from_bytes(_emsa_pss(msg, n.bit_length() - 1, os.urandom(SLEN)), "big")
    r = 0
    while r == 0 or math.gcd(r, n) != 1:
        r = secrets.randbelow(n - 2) + 1
    return (m * pow(r, e, n)) % n, pow(r, -1, n)


def finalize(n: int, blind_sig: int, inv: int) -> bytes:
    return ((blind_sig * inv) % n).to_bytes(math.ceil(n.bit_length() / 8), "big")


def token_verify(n: int, e: int, msg: bytes, sig: bytes) -> bool:
    try:
        rsa.RSAPublicNumbers(e, n).public_key().verify(
            sig, msg, padding.PSS(mgf=padding.MGF1(hashes.SHA384()), salt_length=SLEN), hashes.SHA384())
        return True
    except Exception:  # noqa: BLE001
        return False


class BlindKey:
    """Issuer-side key. The issuer signs blinded values it cannot read."""

    def __init__(self, bits: int = 2048):
        pn = rsa.generate_private_key(public_exponent=65537, key_size=bits).private_numbers()
        self.n, self.e = pn.public_numbers.n, pn.public_numbers.e
        self._p, self._q, self._dp, self._dq, self._qi = pn.p, pn.q, pn.dmp1, pn.dmq1, pn.iqmp

    def blind_sign(self, z: int) -> int:
        s1, s2 = pow(z % self._p, self._dp, self._p), pow(z % self._q, self._dq, self._q)
        s = s2 + self._q * ((self._qi * (s1 - s2)) % self._p)
        if pow(s, self.e, self.n) != z:
            raise ValueError("signing failure")
        return s


# ------------------------------------------------------------- HTTP ---------
class Capture:
    """Everything a process received on the wire, kept for the information-flow scan."""

    def __init__(self):
        self.lock = threading.Lock()
        self.inbound: list[bytes] = []
        self.events: list[dict] = []

    def log(self, **kw):
        with self.lock:
            self.events.append({"t": round(time.time(), 3), **kw})


def serve(port: int, routes: dict, capture: Capture):
    """Blocking JSON-over-HTTP server on 127.0.0.1. routes: path -> fn(dict) -> (code, dict)."""

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a):
            return

        def _reply(self, code: int, obj: dict):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if not self.path.startswith("/_"):
                with capture.lock:
                    capture.inbound.append(self.path.encode() + b"\n" + raw)
            fn = routes.get(self.path)
            if fn is None:
                return self._reply(404, {"error": "not_found"})
            try:
                code, obj = fn(json.loads(raw or b"{}"))
            except Exception as exc:  # noqa: BLE001  fail closed, say why
                code, obj = 500, {"error": "internal", "detail": type(exc).__name__ + ": " + str(exc)[:200]}
            self._reply(code, obj)

    def dump(_req):
        with capture.lock:
            return 200, {"events": list(capture.events)}

    def scan(req):
        """Search everything this process has received for the given byte strings (per named group)."""
        with capture.lock:
            blob = b"\n".join(capture.inbound)
            return 200, {"inbound_messages": len(capture.inbound), "inbound_bytes": len(blob),
                         "found": {g: any(unb64(x) in blob for x in xs) for g, xs in req["groups"].items()}}

    routes["/_capture"] = dump
    routes["/_scan"] = scan
    routes["/_health"] = lambda _r: (200, {"ok": True})
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def post(port: int, path: str, obj: dict, timeout: float = 60.0) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        return 0, {"error": "unreachable", "detail": str(e)[:120]}


def wait_up(port: int, seconds: float = 120.0):
    end = time.time() + seconds
    while time.time() < end:
        if post(port, "/_health", {}, timeout=2.0)[0] == 200:
            return
        time.sleep(0.3)
    raise RuntimeError(f"service on port {port} did not start")


# ------------------------------------------- Merkle log (RFC 9162 hashing) ---
def leaf_hash(b: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + b).digest()


def node_hash(a: bytes, b: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + a + b).digest()


def merkle_levels(leaves: list[bytes]) -> list[list[bytes]]:
    levels = [leaves or [hashlib.sha256(b"").digest()]]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        levels.append([node_hash(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i] for i in range(0, len(cur), 2)])
    return levels


def merkle_proof(levels: list[list[bytes]], idx: int) -> list[list]:
    out = []
    for lvl in levels[:-1]:
        sib = idx ^ 1
        if sib < len(lvl):
            out.append([sib < idx, lvl[sib].hex()])
        idx //= 2
    return out


def merkle_verify(entry: bytes, path: list[list], root_hex: str) -> bool:
    h = leaf_hash(entry)
    for left, sib in path:
        h = node_hash(bytes.fromhex(sib), h) if left else node_hash(h, bytes.fromhex(sib))
    return h.hex() == root_hex
