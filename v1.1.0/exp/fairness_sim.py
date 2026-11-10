"""E3: contribution-weighted admission on a member-contributed pool (simulation).

A discrete-event simulation of one community pool: contributor devices come
and go with their owners' activity, members submit requests, and an admission
policy picks whose request a free device serves next. Three policies are
compared on identical arrival and availability traces per seed:

  fifo        arrival order
  vtc         least-served-first with counter lift (VTC-style, equal weights)
  vtc_contrib least normalised service first; a member's weight grows with the
              service their own devices gave to other members (capped)
  budget      the unlinkable form: the coordinator cannot keep per-member
              counters because tokens hide who is asking, so fairness moves to
              issuance. Each member holds a token bucket refilled in proportion
              to a tier weight (contributors 3, others 1); a request enters the
              pool only when the bucket covers it; the pool itself is FIFO.
  budget_load the same budgets, indexed to pool load: the coordinator publishes
              one aggregate bit (a device is idle and nothing is queued), and
              while it is set the authority issues past the budget, oldest
              waiting request first. The member's bucket goes into debt, so
              surplus use is paid back before that member's next budgeted turn.

Service rates are abstract scenario parameters in tokens per second. They are
not measurements of any THOX device. Owner protection is modelled exactly as
the Auto Device Role Mode contract states it: an owner-active device takes no
community work; work in flight stops at the next 256-token chunk boundary and
the remainder is re-queued.

30 seeds per configuration. Writes exp/results/fairness.json.
"""
from __future__ import annotations

import heapq
import json
import math
import random
import statistics
from pathlib import Path

SEEDS = list(range(30))
HORIZON_S = 8 * 3600.0
CHUNK = 256
DEVICE_RATES = [8.0] * 6 + [15.0] * 4 + [30.0] * 2      # 12 contributor devices
MEMBERS = 40                                             # members 0..11 own the devices
HEAVY = (38, 39)                                         # two non-contributors at 10x demand
HEAVY_FACTOR = 10.0
MEAN_IDLE_S, MEAN_ACTIVE_S = 40 * 60.0, 20 * 60.0        # owner away / owner using the device
TOK_MEDIAN, TOK_SIGMA = 300.0, 0.8
BETA, W_MAX = 2.0, 4.0
LOADS = [0.6, 0.8, 1.0, 1.2, 1.4]
POLICIES = ["fifo", "vtc", "vtc_contrib", "budget", "budget_load"]
TIER_W = 3.0            # budget policy: contributor tier weight
OVERCOMMIT = 1.25       # budget policy: issued service over expected capacity
BURST_S = 600.0         # budget policy: bucket depth in seconds of refill

AVAIL = MEAN_IDLE_S / (MEAN_IDLE_S + MEAN_ACTIVE_S)
CAPACITY = sum(DEVICE_RATES) * AVAIL
MEAN_TOK = TOK_MEDIAN * math.exp(TOK_SIGMA ** 2 / 2)
DEMAND_UNITS = (MEMBERS - len(HEAVY)) + HEAVY_FACTOR * len(HEAVY)


def make_trace(seed: int, load: float):
    """Arrivals and owner-activity intervals; identical across policies."""
    rng = random.Random(seed * 1000 + int(load * 100))
    lam_unit = load * CAPACITY / (DEMAND_UNITS * MEAN_TOK)
    arrivals = []
    for m in range(MEMBERS):
        lam = lam_unit * (HEAVY_FACTOR if m in HEAVY else 1.0)
        t = rng.expovariate(lam)
        while t < HORIZON_S:
            tokens = max(16, int(rng.lognormvariate(math.log(TOK_MEDIAN), TOK_SIGMA)))
            arrivals.append((t, m, tokens))
            t += rng.expovariate(lam)
    arrivals.sort()
    toggles = []                                         # (time, device, owner_active)
    for d in range(len(DEVICE_RATES)):
        t, active = 0.0, rng.random() > AVAIL
        if active:
            toggles.append((0.0, d, True))
        while t < HORIZON_S:
            t += rng.expovariate(1.0 / (MEAN_ACTIVE_S if active else MEAN_IDLE_S))
            active = not active
            toggles.append((t, d, active))
    return arrivals, toggles


def simulate(policy: str, arrivals, toggles):
    n_dev = len(DEVICE_RATES)
    queues: dict[int, list] = {m: [] for m in range(MEMBERS)}    # per member FIFO of [arrival, remaining, first_start]
    served = [0.0] * MEMBERS          # tokens of service received
    counter = [0.0] * MEMBERS         # VTC virtual counter
    credit = [0.0] * MEMBERS          # tokens the member's device served for other members
    owner_active = [False] * n_dev
    busy = [None] * n_dev             # (member, request) in flight
    waits: dict[int, list] = {m: [] for m in range(MEMBERS)}
    owner_delay = []                  # seconds from owner return to device free
    pending_owner = {}
    events = []
    seq = 0
    n_devs = len(DEVICE_RATES)
    wts = [TIER_W if m < n_devs else 1.0 for m in range(MEMBERS)]
    rate = [OVERCOMMIT * CAPACITY * w / sum(wts) for w in wts]
    bucket = [r * BURST_S for r in rate]
    stamp = [0.0] * MEMBERS
    gate: dict[int, list] = {m: [] for m in range(MEMBERS)}
    surplus = [0.0]

    def release(m: int, now: float):
        nonlocal seq
        bucket[m] = min(rate[m] * BURST_S, bucket[m] + rate[m] * (now - stamp[m]))
        stamp[m] = now
        while gate[m]:
            need = min(gate[m][0][1], rate[m] * BURST_S)
            if bucket[m] + 1e-9 < need:
                heapq.heappush(events, (now + (need - bucket[m]) / rate[m] + 1e-6, seq, "refill", m)); seq += 1
                return
            req = gate[m].pop(0)
            bucket[m] -= req[1]
            req[3] = now
            queues[m].append(req)

    for t, m, tok in arrivals:
        heapq.heappush(events, (t, seq, "arrive", (m, tok))); seq += 1
    for t, d, a in toggles:
        heapq.heappush(events, (t, seq, "toggle", (d, a))); seq += 1

    def weight(m: int) -> float:
        if policy != "vtc_contrib" or m >= n_dev:
            return 1.0
        pos = [c for c in credit[:n_dev] if c > 0]
        if not pos or credit[m] <= 0:
            return 1.0
        return min(W_MAX, 1.0 + BETA * credit[m] / (sum(pos) / len(pos)))

    def pick(now: float):
        active = [m for m in range(MEMBERS) if queues[m]]
        if not active:
            return None
        if policy == "fifo":
            return min(active, key=lambda m: queues[m][0][0])
        if policy in ("budget", "budget_load"):
            return min(active, key=lambda m: queues[m][0][3])
        return min(active, key=lambda m: (counter[m] / weight(m), queues[m][0][0]))

    def dispatch(now: float):
        nonlocal seq
        for d in sorted(range(n_dev), key=lambda i: -DEVICE_RATES[i]):
            if busy[d] is not None or owner_active[d]:
                continue
            m = pick(now)
            if m is None and policy == "budget_load":
                waiting = [x for x in range(MEMBERS) if gate[x]]
                if waiting:                                   # pool idle: issue past the budget, oldest first
                    x = min(waiting, key=lambda y: gate[y][0][0])
                    bucket[x] = min(rate[x] * BURST_S, bucket[x] + rate[x] * (now - stamp[x]))
                    stamp[x] = now
                    req0 = gate[x].pop(0)
                    bucket[x] -= req0[1]                      # debt is repaid before the next budgeted turn
                    req0[3] = now
                    queues[x].append(req0)
                    surplus[0] += req0[1]
                    m = x
            if m is None:
                return
            req = queues[m].pop(0)
            if req[2] is None:
                req[2] = now
                waits[m].append(now - req[0])
            busy[d] = (m, req)
            n = min(CHUNK, req[1])
            heapq.heappush(events, (now + n / DEVICE_RATES[d], seq, "chunk", (d, n))); seq += 1

    while events:
        now, _, kind, data = heapq.heappop(events)
        if now > HORIZON_S:
            break
        if kind == "arrive":
            m, tok = data
            if policy in ("budget", "budget_load"):
                gate[m].append([now, tok, None, now])
                release(m, now)
                dispatch(now)
                continue
            if not queues[m] and policy != "fifo":
                others = [counter[x] for x in range(MEMBERS) if queues[x] and x != m]
                if others:
                    counter[m] = max(counter[m], min(others))       # counter lift: no banked idle credit
            queues[m].append([now, tok, None, now])
        elif kind == "refill":
            release(data, now)
        elif kind == "toggle":
            d, a = data
            owner_active[d] = a
            if a and busy[d] is not None:
                pending_owner[d] = now                              # in-flight chunk finishes, then yields
            elif a:
                owner_delay.append(0.0)
        else:
            d, n = data
            m, req = busy[d]
            req[1] -= n
            served[m] += n
            counter[m] += n
            if m != d:                                              # device d belongs to member d
                credit[d] += n
            if d in pending_owner:
                owner_delay.append(now - pending_owner.pop(d))
            if req[1] > 0 and not owner_active[d]:
                nn = min(CHUNK, req[1])
                heapq.heappush(events, (now + nn / DEVICE_RATES[d], seq, "chunk", (d, nn))); seq += 1
                continue
            busy[d] = None
            if req[1] > 0:
                queues[m].insert(0, req)                            # owner returned: remainder re-queued
        dispatch(now)

    def group(ms):
        w = [x for m in ms for x in waits[m]]
        if not w:
            return {"n": 0, "mean_wait_s": 0.0, "p95_wait_s": 0.0}
        w.sort()
        return {"n": len(w), "mean_wait_s": sum(w) / len(w), "p95_wait_s": w[int(0.95 * (len(w) - 1))]}

    contributors = list(range(n_dev))
    others = [m for m in range(n_dev, MEMBERS) if m not in HEAVY]
    total = sum(served) or 1.0
    return {
        "contributors": group(contributors), "others": group(others), "heavy": group(HEAVY),
        "heavy_service_share": sum(served[m] for m in HEAVY) / total,
        "contributor_service_share": sum(served[m] for m in contributors) / total,
        "served_tokens": total, "surplus_tokens": surplus[0],
        "owner_delay_max_s": max(owner_delay) if owner_delay else 0.0,
        "owner_delay_mean_s": sum(owner_delay) / len(owner_delay) if owner_delay else 0.0,
        "owner_returns": len(owner_delay),
    }


def main() -> int:
    out = {"params": {"seeds": len(SEEDS), "horizon_s": HORIZON_S, "chunk_tokens": CHUNK,
                      "device_rates_tok_s": DEVICE_RATES, "members": MEMBERS, "heavy_members": len(HEAVY),
                      "heavy_factor": HEAVY_FACTOR, "availability": AVAIL, "capacity_tok_s": CAPACITY,
                      "beta": BETA, "w_max": W_MAX, "loads": LOADS,
                      "worst_chunk_s": CHUNK / min(DEVICE_RATES)},
           "runs": []}
    for load in LOADS:
        for seed in SEEDS:
            arrivals, toggles = make_trace(seed, load)
            for pol in POLICIES:
                r = simulate(pol, arrivals, toggles)
                out["runs"].append({"load": load, "seed": seed, "policy": pol, **r})
        done = [r for r in out["runs"] if r["load"] == load]
        for pol in POLICIES:
            xs = [r["contributors"]["p95_wait_s"] for r in done if r["policy"] == pol]
            hs = [r["heavy_service_share"] for r in done if r["policy"] == pol]
            print(f"load {load} {pol:12s} contributor p95 wait median {statistics.median(xs):8.1f} s  heavy share {statistics.median(hs):.3f}")
    Path(__file__).with_name("results").joinpath("fairness.json").write_text(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
