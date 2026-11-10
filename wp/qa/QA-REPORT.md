# QA Report — Community MeshStack paper v1.0.0 (internal edition)

- Render: WeasyPrint from wp/paper.src.html; 13 pages; cover, KPI cards, Figures 1-5 and Table 1 inspected on rendered pages 1 and 7 (contact renders in wp/qa/page-*.png).
- Numbers: every lab number in the paper is read by wp/build_paper.py from exp/results/summary.json; no hand-typed lab numbers.
- Lab tests: exp/test_lab.py 5/5 pass (whole-request, household negative result, 2-stage 27B, P0 foreground exclusion, privacy drills).
- Blocker sweep (Process v1.0 §4, internal edition): no template placeholders in body text; byline Craig Ross first, Tommy Xaypanya corresponding, ORCID on file for Xaypanya only; no confidentiality markings; no host names, network addresses, credentials or lane internals in the pack (repository names and commit SHAs are the paper's cited evidence base, as in the household paper); THOX casing verified.
- Second pass (not independent review): Sadie re-read summary.json values against the rendered Table 1 and Section 5/7 numbers after the build; GitHub and literature inputs were produced by separate review lanes and cross-checked against their source reports.
- Known limits: TikZ figure labels are small at print size (source ships in bundle); DOCX is a LibreOffice conversion of the shipped HTML and is the editable copy, PDF is the reading copy.
