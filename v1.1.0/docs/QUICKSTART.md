# Quick start (commands run on 2026-11-10, Linux x86_64, 2 vCPU, 7 GB, Python 3.13)

```
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers safetensors cryptography numpy matplotlib pypdf pillow
python3 exp/audit_experiments.py          # about 10 minutes; downloads SmolLM2-135M-Instruct
(cd exp && python3 audit_timing.py)       # about 5 minutes
python3 exp/token_experiments.py          # about 1 minute
python3 exp/fairness_sim.py               # about 3 minutes
python3 exp/ledger_experiments.py
python3 -m lab.run_lab                    # about 3 minutes; needs about 5 GB RAM
python3 exp/analyze.py
cd wp && npm install && cd ..
python3 wp/figures.py && python3 wp/build.py
node wp/katex_render.cjs wp/paper.src.html wp/paper.html
node wp/pdf.cjs wp/paper.html wp/cover.pdf wp/body.pdf && python3 wp/merge_pdf.py
python3 wp/build_demo.py && python3 wp/build_docs.py
node wp/qa.cjs && python3 wp/qa_pdf.py    # needs Playwright and poppler-utils
```

Do not run anything else on the host during the timed experiments.
