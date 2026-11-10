# User guide

**Read the paper:** open `dist/THOX_Community_Mesh_Paper_v1.1.0.pdf` or `dist/THOX_Community_Mesh_Paper_v1.1.0.html`.

**Try the mechanisms:** open `dist/THOX_Community_Mesh_Demo_v1.1.0.html` in any browser. It runs offline. The green chips at the top are known-answer tests; all seven must say pass. Then:

1. Issue a token, redeem it, redeem it again (the second is refused).
2. Pick a cheat and move the audit-rate slider to see how fast it is caught.
3. Change the queue mix and weight and grant in order.
4. Seal an epoch, prove an entry, tamper with it, then let the operator try to rewrite history.

**Run the lab:** `python3 -m lab.run_lab` from this folder. It starts 14 local processes, runs every scenario and writes `lab/evidence/evidence.json`, `lab/evidence/transcript.log` and one event log per process. Exit code 0 means every scenario passed.

**What the lab is not:** THOX hardware, a network, or a performance test.
