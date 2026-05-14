#!/usr/bin/env python3
"""
Embed wta_data.json into wta_graph.html → index.html (GitHub Pages ready).

Run after fetch_wta_data.py:
    python3 build.py

Then commit & push index.html to your GitHub Pages branch.
"""

import json, sys, pathlib

DATA_FILE     = pathlib.Path("wta_data.json")
TEMPLATE_FILE = pathlib.Path("wta_graph.html")
OUTPUT_FILE   = pathlib.Path("index.html")

PLACEHOLDER = "null /* WTA_DATA_PLACEHOLDER */"


def main():
    if not DATA_FILE.exists():
        sys.exit(f"✗ {DATA_FILE} not found. Run python3 fetch_wta_data.py first.")

    if not TEMPLATE_FILE.exists():
        sys.exit(f"✗ {TEMPLATE_FILE} not found.")

    with DATA_FILE.open(encoding="utf-8") as f:
        data = json.load(f)

    players = data.get("players", [])
    h2h     = data.get("h2h", {})

    if not players:
        sys.exit("✗ wta_data.json contains no players. Re-run fetch_wta_data.py.")

    total_matches = sum(
        (v.get("player1_wins", 0) + v.get("player2_wins", 0)) for v in h2h.values()
    )
    print(f"  Players:  {len(players)}")
    print(f"  Matchups: {len(h2h)}  ({total_matches} total matches)")

    template = TEMPLATE_FILE.read_text(encoding="utf-8")

    if PLACEHOLDER not in template:
        sys.exit(f"✗ Placeholder '{PLACEHOLDER}' not found in {TEMPLATE_FILE}. "
                 "Make sure you haven't already embedded data manually.")

    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    output   = template.replace(PLACEHOLDER, embedded, 1)

    OUTPUT_FILE.write_text(output, encoding="utf-8")
    size_kb = OUTPUT_FILE.stat().st_size / 1024
    print(f"\n✓ Built {OUTPUT_FILE}  ({size_kb:.0f} KB)")
    print("  Commit and push index.html to enable GitHub Pages.")


if __name__ == "__main__":
    main()
