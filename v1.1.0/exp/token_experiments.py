"""E2: cost of the identity-hiding path: blind-signed subscriber tokens and a
sealed relay envelope.

(a) RSA blind signatures per RFC 9474 (RSABSSA-SHA384-PSS). The EMSA-PSS
    encoding, blinding, CRT blind-signing and finalisation are implemented here
    in plain Python integers and checked two ways: against the RFC 9474
    Appendix A.3 deterministic test vector, and by verifying every finalised
    signature with the `cryptography` library's independent RSASSA-PSS verifier.
    Timed at 2048 and 4096 bits.
(b) HPKE base mode (RFC 9180; X25519, HKDF-SHA256, ChaCha20-Poly1305) from the
    `cryptography` library: seal and open time and byte overhead by payload
    size. This is the envelope a relay forwards without being able to read.

Pure-Python big-integer timings are an upper bound on what a native
implementation would cost; they are reported as measured on this host.
Writes exp/results/token.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import secrets
import statistics
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, hpke
from cryptography.hazmat.primitives.asymmetric import padding, rsa, x25519

HERE = Path(__file__).resolve().parent
RUNS = 200
RUNS_4096 = 60
SLEN = 48


def mgf1(seed: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hashlib.sha384(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:length]


def emsa_pss_encode(msg: bytes, em_bits: int, salt: bytes) -> bytes:
    """RFC 8017 section 9.1.1 with SHA-384 and MGF1-SHA-384."""
    m_hash = hashlib.sha384(msg).digest()
    h_len = len(m_hash)
    em_len = math.ceil(em_bits / 8)
    if em_len < h_len + len(salt) + 2:
        raise ValueError("encoding error")
    h = hashlib.sha384(b"\x00" * 8 + m_hash + salt).digest()
    ps = b"\x00" * (em_len - len(salt) - h_len - 2)
    db = ps + b"\x01" + salt
    mask = mgf1(h, em_len - h_len - 1)
    masked = bytearray(a ^ b for a, b in zip(db, mask))
    masked[0] &= 0xFF >> (8 * em_len - em_bits)
    return bytes(masked) + h + b"\xbc"


def blind(n: int, e: int, msg: bytes, salt: bytes | None = None, r: int | None = None):
    salt = os.urandom(SLEN) if salt is None else salt
    m = int.from_bytes(emsa_pss_encode(msg, n.bit_length() - 1, salt), "big")
    if math.gcd(m, n) != 1:
        raise ValueError("invalid input")
    while r is None or math.gcd(r, n) != 1:
        r = secrets.randbelow(n - 2) + 1
    inv = pow(r, -1, n)
    return (m * pow(r, e, n)) % n, inv


def blind_sign_crt(z: int, p: int, q: int, dp: int, dq: int, qinv: int, n: int, e: int) -> int:
    s1, s2 = pow(z % p, dp, p), pow(z % q, dq, q)
    s = s2 + q * ((qinv * (s1 - s2)) % p)
    if pow(s, e, n) != z:  # RFC 9474 section 4.3: verify before release
        raise ValueError("signing failure")
    return s


def finalize(n: int, blind_sig: int, inv: int) -> bytes:
    return ((blind_sig * inv) % n).to_bytes(math.ceil(n.bit_length() / 8), "big")


def lib_verify(n: int, e: int, msg: bytes, sig: bytes) -> bool:
    pub = rsa.RSAPublicNumbers(e, n).public_key()
    try:
        pub.verify(sig, msg, padding.PSS(mgf=padding.MGF1(hashes.SHA384()), salt_length=SLEN), hashes.SHA384())
        return True
    except Exception:  # noqa: BLE001
        return False


def known_answer() -> dict:
    v = json.loads((HERE / "rfc9474_a3.json").read_text())["vector"]
    p, q, n, e, d = (int(v[k], 16) for k in ("p", "q", "n", "e", "d"))
    msg, salt = bytes.fromhex(v["prepared_msg"]), bytes.fromhex(v["salt"])
    enc = emsa_pss_encode(msg, n.bit_length() - 1, salt)
    r = pow(int(v["inv"], 16), -1, n)
    z, inv = blind(n, e, msg, salt=salt, r=r)
    bs = blind_sign_crt(z, p, q, d % (p - 1), d % (q - 1), pow(q, -1, p), n, e)
    sig = finalize(n, bs, inv)
    return {
        "encoded_msg_match": enc.hex() == v["encoded_msg"],
        "blinded_msg_match": f"{z:0{len(v['blinded_msg'])}x}" == v["blinded_msg"],
        "blind_sig_match": f"{bs:0{len(v['blind_sig'])}x}" == v["blind_sig"],
        "sig_match": sig.hex() == v["sig"],
        "library_verifies": lib_verify(n, e, msg, sig),
    }


def time_blind_rsa(bits: int, runs: int) -> dict:
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    pn = key.private_numbers()
    n, e = pn.public_numbers.n, pn.public_numbers.e
    t = {"blind": [], "blind_sign": [], "finalize": [], "verify": []}
    ok = 0
    for i in range(runs + 5):
        msg = os.urandom(32)
        a = time.perf_counter(); z, inv = blind(n, e, msg)
        b = time.perf_counter(); bs = blind_sign_crt(z, pn.p, pn.q, pn.dmp1, pn.dmq1, pn.iqmp, n, e)
        c = time.perf_counter(); sig = finalize(n, bs, inv)
        d = time.perf_counter(); good = lib_verify(n, e, msg, sig)
        f = time.perf_counter()
        if i >= 5:  # first five are warm-up
            for k, val in zip(t, (b - a, c - b, d - c, f - d)):
                t[k].append(val * 1e3)
            ok += good
    def q(xs):
        qs = statistics.quantiles(xs, n=4)
        return {"median_ms": statistics.median(xs), "q1_ms": qs[0], "q3_ms": qs[2]}
    return {"bits": bits, "runs": runs, "verified": ok, "token_bytes": math.ceil(bits / 8),
            **{k: q(v) for k, v in t.items()}}


def time_hpke(runs: int) -> list[dict]:
    suite = hpke.Suite(hpke.KEM.X25519, hpke.KDF.HKDF_SHA256, hpke.AEAD.CHACHA20_POLY1305)
    sk = x25519.X25519PrivateKey.generate()
    pk = sk.public_key()
    info = b"thox.community.relay.v1"
    rows = []
    for size in (256, 1024, 4096, 16384, 65536):
        seal, opn, over = [], [], 0
        for i in range(runs + 5):
            pt = os.urandom(size)
            a = time.perf_counter(); ct = suite.encrypt(pt, pk, info)
            b = time.perf_counter(); back = suite.decrypt(ct, sk, info)
            c = time.perf_counter()
            assert back == pt
            over = len(ct) - size
            if i >= 5:
                seal.append((b - a) * 1e6); opn.append((c - b) * 1e6)
        rows.append({"payload_bytes": size, "overhead_bytes": over, "runs": runs,
                     "seal_median_us": statistics.median(seal), "seal_q1_us": statistics.quantiles(seal, n=4)[0],
                     "seal_q3_us": statistics.quantiles(seal, n=4)[2],
                     "open_median_us": statistics.median(opn), "open_q1_us": statistics.quantiles(opn, n=4)[0],
                     "open_q3_us": statistics.quantiles(opn, n=4)[2]})
    return rows


def main() -> int:
    out = {
        "host": {"machine": platform.machine(), "python": platform.python_version()},
        "kat_rfc9474_a3": known_answer(),
        "blind_rsa": [time_blind_rsa(2048, RUNS), time_blind_rsa(4096, RUNS_4096)],
        "hpke": time_hpke(RUNS),
    }
    (HERE / "results" / "token.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
