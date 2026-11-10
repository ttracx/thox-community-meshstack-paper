"""Render every PDF page to a contact sheet for visual QA and grep outputs for em dashes and placeholders."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "dist" / "THOX_Community_Mesh_Paper_v1.1.0.pdf"
QA = ROOT / "wp" / "qa"
QA.mkdir(exist_ok=True)

for old in QA.glob("page-*.png"):
    old.unlink()
subprocess.run(["pdftoppm", "-r", "45", "-png", str(PDF), str(QA / "page")], check=True)
pages = sorted(QA.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
imgs = [Image.open(p) for p in pages]
w, h = imgs[0].size
cols = 5
rows = (len(imgs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (w + 10) + 10, rows * (h + 10) + 10), "#DDDDDD")
for i, im in enumerate(imgs):
    sheet.paste(im, (10 + (i % cols) * (w + 10), 10 + (i // cols) * (h + 10)))
sheet.save(QA / "contact_sheet.png")
print("pages", len(imgs), "sheet", QA / "contact_sheet.png")

text = subprocess.run(["pdftotext", str(PDF), "-"], capture_output=True, text=True, check=True).stdout
bad = {"em dash": text.count("—"), "TODO": len(re.findall(r"\bTODO\b", text)), "lorem": text.lower().count("lorem"),
       "placeholder": text.lower().count("placeholder"), "XXX": text.count("XXX")}
print("pdf text checks", bad)
for f in [ROOT / "wp" / "paper.html", ROOT / "dist" / "THOX_Community_Mesh_Demo_v1.1.0.html"]:
    t = f.read_text()
    print(f.name, "em dashes:", t.count("—"), "TODO:", len(re.findall(r"\bTODO\b", t)))
sys.exit(0 if bad["em dash"] == 0 and bad["TODO"] == 0 else 1)
