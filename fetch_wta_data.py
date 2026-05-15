#!/usr/bin/env python3
"""
Fetch WTA Top 20 rankings + all 190 H2H matchups.
Run once:  python3 fetch_wta_data.py
Output:    wta_data.json  (feed into build.py)

Requirements: Python 3.8+, no external libraries needed.
"""

import json, time, re, sys, urllib.request, urllib.error
from itertools import combinations

RATE_LIMIT = 0.15   # seconds between API calls

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/html, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.wtatennis.com/",
    "Origin":          "https://www.wtatennis.com",
}


# ── HTTP helper ────────────────────────────────────────────────────────────────
def fetch(url, accept="application/json"):
    h = dict(HEADERS)
    h["Accept"] = accept
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read()
        if "json" in accept:
            return json.loads(raw)
        return raw.decode("utf-8", errors="ignore")


# ── Rankings ───────────────────────────────────────────────────────────────────
def get_top20():
    print("► Fetching WTA Top 20 rankings …")

    # Strategy 1: official rankings API
    api_urls = [
        "https://api.wtatennis.com/tennis/rankings/singles?page=0&pageSize=20",
        "https://api.wtatennis.com/tennis/rankings?type=singles&limit=20&pageSize=20",
    ]
    for url in api_urls:
        try:
            data = fetch(url)
            players = _parse_rankings_api(data)
            if players:
                print(f"  Got {len(players)} players from API ✓")
                return players
        except Exception as e:
            print(f"  API {url}: {e}")

    # Strategy 2: scrape rankings page HTML for /players/player/{id}/{slug} links
    print("  Falling back to HTML scrape …")
    try:
        html = fetch("https://www.wtatennis.com/rankings/singles",
                     accept="text/html,application/xhtml+xml,*/*;q=0.8")
        players = _parse_rankings_html(html)
        if players:
            print(f"  Got {len(players)} players from HTML ✓")
            return players
    except Exception as e:
        print(f"  HTML scrape: {e}")

    raise RuntimeError(
        "Could not fetch rankings. Check your internet connection "
        "or try running the script in a browser network tab."
    )


def _parse_rankings_api(data):
    """Handle multiple possible API response shapes."""
    entries = data if isinstance(data, list) else data.get("data", data.get("rankings", []))
    players = []
    for i, entry in enumerate(entries[:20], 1):
        pl = entry.get("player", entry)
        fname = pl.get("firstName", pl.get("first_name", ""))
        lname = pl.get("lastName",  pl.get("last_name",  ""))
        name  = f"{fname} {lname}".strip() or pl.get("name", pl.get("playerName", "Unknown"))
        pid   = str(pl.get("id", pl.get("playerId", pl.get("player_id", ""))))
        if not pid:
            continue
        players.append({
            "id":      pid,
            "rank":    int(entry.get("rank", entry.get("ranking", i))),
            "name":    name,
            "country": pl.get("nationality", pl.get("countryCode", pl.get("country", "UNK"))),
            "points":  int(entry.get("points", entry.get("rankingPoints", 0)) or 0),
            "titles":  int(pl.get("titles", pl.get("titleCount", 0)) or 0),
            "slug":    pl.get("slug", ""),
        })
    return players


def _parse_rankings_html(html):
    """Extract player IDs + slugs from /players/{id}/{slug} links."""
    hits = re.findall(r"/players/(\d[\d,]*)/([^\"\s<>/]+)", html)
    seen, players = set(), []
    for pid_raw, slug in hits:
        if pid_raw in seen or len(players) >= 20:
            continue
        seen.add(pid_raw)
        pid = pid_raw.replace(",", "")
        name = re.sub(r"-+", " ", slug).title()
        players.append({
            "id":      pid,
            "rank":    len(players) + 1,
            "name":    name,
            "country": "UNK",
            "points":  0,
            "titles":  0,
            "slug":    slug,
        })
    return players


# ── Player enrichment (optional — fills country/points if HTML scrape was used) ─
def enrich_player(p):
    """Try to pull country & points from the player profile API."""
    if p["country"] not in ("UNK", ""):
        return p
    try:
        data = fetch(f"https://api.wtatennis.com/tennis/players/{p['id']}")
        p["country"] = data.get("nationality", data.get("countryCode", "UNK"))
        p["titles"]  = int(data.get("titles", data.get("titleCount", 0)) or 0)
        slug = data.get("slug", "")
        if slug:
            p["slug"] = slug
        time.sleep(RATE_LIMIT)
    except Exception:
        pass
    return p


# ── H2H ────────────────────────────────────────────────────────────────────────
def get_h2h(id1, id2):
    url = f"https://api.wtatennis.com/tennis/players/{id1}/headtohead/{id2}"
    try:
        data = fetch(url)
        summary = (data.get("headToHeadSummary") or [{}])[0]
        raw_matches = data.get("matchEncounterResults") or []

        matches = []
        for m in raw_matches:
            tourn = (m.get("TournamentName")
                     or m.get("tournamentName")
                     or "")
            w = m.get("winner")
            if isinstance(w, int):
                winner_id = str(m.get(f"player_{w}", ""))
            else:
                winner_id = str(m.get("winnerId", ""))
            matches.append({
                "date":       m.get("StartDate") or m.get("date") or "",
                "tournament": tourn,
                "round":      m.get("round_name") or m.get("roundName") or "",
                "winner_id":  winner_id,
                "score":      m.get("scores") or m.get("score") or "",
            })

        return {
            "player1_wins": int(summary.get("wins",   0) or 0),
            "player2_wins": int(summary.get("losses", 0) or 0),
            "matches":      matches,
        }
    except Exception as e:
        print(f"    ⚠ H2H {id1}×{id2}: {e}")
        return {"player1_wins": 0, "player2_wins": 0, "matches": []}


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    players = get_top20()

    # Enrich any players whose country is still unknown
    needs_enrich = [p for p in players if p["country"] in ("UNK", "")]
    if needs_enrich:
        print(f"  Enriching {len(needs_enrich)} players …")
        players = [enrich_player(p) for p in players]

    print()
    print("  #  Player                  Country  Points")
    print("  " + "─" * 48)
    for p in players:
        print(f"  {p['rank']:2d}  {p['name']:<22}  {p['country']:<5}  {p['points']:,}")

    pairs = list(combinations(players, 2))
    total_pairs = len(pairs)
    eta_min = total_pairs * RATE_LIMIT / 60
    print(f"\n► Fetching {total_pairs} H2H matchups (~{eta_min:.1f} min) …\n")

    h2h = {}
    for i, (p1, p2) in enumerate(pairs, 1):
        key = f"{p1['id']}-{p2['id']}"
        print(f"  [{i:3d}/{total_pairs}] {p1['name']} vs {p2['name']} ", end="", flush=True)

        result = get_h2h(p1["id"], p2["id"])
        result["player1_id"] = p1["id"]
        result["player2_id"] = p2["id"]
        h2h[key] = result

        total = result["player1_wins"] + result["player2_wins"]
        print(f"→ {result['player1_wins']}–{result['player2_wins']} ({total} matches)")
        time.sleep(RATE_LIMIT)

    output = {"players": players, "h2h": h2h}
    with open("wta_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved wta_data.json  ({len(players)} players, {len(h2h)} matchups)")
    print("  Next: python3 build.py")


if __name__ == "__main__":
    main()
