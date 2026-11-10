"""Fetch exact arXiv metadata for every candidate reference and record it.

Writes wp/refs_raw.json with title, authors (in order), published and updated
dates, and the abs URL, straight from the arXiv export API. Nothing is typed
from memory. Entries that fail to resolve are recorded as unresolved.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

CANDIDATES = {
    "petals": "2209.01188",
    "petalsinternet": "2312.08361",
    "vtc": "2401.00588",
    "boinc": "1903.01699",
    "pia": "2503.09022",
    "piadef": "2606.11592",
    "toploc": "2501.16007",
    "svip": "2410.22307",
    "pos": "2405.00295",
    "vec2text": "2310.06816",
    "lmi": "2311.13647",
    "opml": "2401.17555",
    "dlpm": "2501.14312",
    "parallax": "2509.26182",
    "poq": "2512.16317",
    "primacpp": "2504.08791",
    "teecost": "2509.18886",
    "fairinference": "2609.18112",
    "puma": "2307.12533",
}


def fetch(ids: list[str]) -> dict[str, dict]:
    url = "https://export.arxiv.org/api/query?id_list=" + ",".join(ids) + f"&max_results={len(ids)}"
    req = urllib.request.Request(url, headers={"User-Agent": "thox-refs-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    out: dict[str, dict] = {}
    for entry in root.findall("a:entry", NS):
        eid = entry.findtext("a:id", default="", namespaces=NS)
        arxiv_id = eid.rsplit("/abs/", 1)[-1]
        base = arxiv_id.split("v")[0]
        title = " ".join(entry.findtext("a:title", default="", namespaces=NS).split())
        authors = [" ".join(a.findtext("a:name", default="", namespaces=NS).split())
                   for a in entry.findall("a:author", NS)]
        out[base] = {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "published": entry.findtext("a:published", default="", namespaces=NS),
            "updated": entry.findtext("a:updated", default="", namespaces=NS),
            "journal_ref": entry.findtext("arxiv:journal_ref", default="", namespaces=NS),
            "doi": entry.findtext("arxiv:doi", default="", namespaces=NS),
            "url": f"https://arxiv.org/abs/{base}",
        }
    return out


def main() -> int:
    ids = list(CANDIDATES.values())
    got: dict[str, dict] = {}
    for i in range(0, len(ids), 10):
        chunk = ids[i:i + 10]
        for attempt in range(3):
            try:
                got.update(fetch(chunk))
                break
            except Exception as exc:  # noqa: BLE001
                print("retry", chunk, exc, file=sys.stderr)
                time.sleep(3)
        time.sleep(3)
    result = {}
    for key, aid in CANDIDATES.items():
        if aid in got and got[aid]["title"]:
            result[key] = got[aid] | {"status": "resolved"}
        else:
            result[key] = {"arxiv_id": aid, "status": "unresolved"}
    Path(__file__).with_name("refs_raw.json").write_text(json.dumps(result, indent=2))
    for key, rec in result.items():
        print(f"{key:14s} {rec['status']:10s} {rec.get('arxiv_id','')}: {rec.get('title','')[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
