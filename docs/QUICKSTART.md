# Quickstart — THOX Community MeshStack Paper

Five minutes from zero to verified evidence. Requirements: Python 3.10+ (stdlib only for the lab), a PDF reader.

## 1. Clone

```bash
git clone https://github.com/ttracx/thox-community-meshstack-paper.git
cd thox-community-meshstack-paper
```

## 2. Read the paper

Open `dist/THOX_Community_MeshStack_Research_Paper_v1.0.0.pdf` (reading copy). The identical content is in `dist/THOX_Community_MeshStack_Research_Paper_v1.0.0.html`; the editable copy is the DOCX in the same folder.

## 3. Try the demo

Open `dist/Community_MeshStack_Demo_v1.0.0.html` in any browser. Pick a model and a hardware pool; the planner applies the paper's two-domain admission rule in your browser and returns a whole-request placement, a pipeline plan, or a fail-closed Unplaceable.

## 4. Regenerate the evidence

```bash
python3 exp/community_lab.py > exp/results/summary.json
python3 exp/test_lab.py
```

All five tests pass, and every number in the paper's Table 1 and Sections 5 and 7 traces to `exp/results/summary.json`.

## 5. Rebuild the paper (optional)

```bash
python3 wp/figures.py
python3 wp/build_paper.py
```

This regenerates the figures and `wp/paper.src.html` from `summary.json`. Rendering the PDF from that HTML uses WeasyPrint.

Next: the full [User Guide](USER_GUIDE.md).
