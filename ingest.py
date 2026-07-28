"""
Pulls today's real MLB slate and writes slate.json for the model.

Sources:
  - statsapi.mlb.com  (free, no key)  -> schedule, probable starters,
                                         standings, team pitching
  - the-odds-api.com  (free key)      -> moneyline, run line, totals

If no odds key is present the slate is still built, with markets omitted.
The dashboard then shows projections only, no EV.
"""

import datetime as dt
import json
import os
import sys
import time
import urllib.parse

import requests

MLB = "https://statsapi.mlb.com/api/v1"
ODDS = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
SEASON = dt.date.today().year
UA = {"User-Agent": "slate-model/1.0"}

# Runs park factors, 100 = neutral, expressed as multipliers.
# Update yearly from Statcast park factors; these are stable enough year to year.
PARK = {
    "COL": 1.18, "CIN": 1.07, "BOS": 1.05, "ATH": 1.06, "ARI": 1.04,
    "CHC": 1.03, "NYY": 1.03, "BAL": 1.02, "TEX": 1.02, "CHW": 1.02,
    "KCR": 1.01, "PHI": 1.01, "WSN": 1.01, "LAA": 1.01, "TOR": 1.01,
    "MIN": 1.00, "ATL": 1.00, "MIL": 1.00, "LAD": 1.00, "HOU": 0.99,
    "DET": 0.99, "STL": 0.99, "NYM": 0.98, "CLE": 0.98, "TBR": 0.97,
    "PIT": 0.97, "MIA": 0.96, "SDP": 0.95, "SEA": 0.94, "SFG": 0.94,
}

# statsapi team id -> (abbr, short display name)
TEAMS = {
    108: ("LAA", "Los Angeles"), 109: ("ARI", "Arizona"), 110: ("BAL", "Baltimore"),
    111: ("BOS", "Boston"), 112: ("CHC", "Chicago"), 113: ("CIN", "Cincinnati"),
    114: ("CLE", "Cleveland"), 115: ("COL", "Colorado"), 116: ("DET", "Detroit"),
    117: ("HOU", "Houston"), 118: ("KCR", "Kansas City"), 119: ("LAD", "Los Angeles"),
    120: ("WSN", "Washington"), 121: ("NYM", "New York"), 133: ("ATH", "Athletics"),
    134: ("PIT", "Pittsburgh"), 135: ("SDP", "San Diego"), 136: ("SEA", "Seattle"),
    137: ("SFG", "San Francisco"), 138: ("STL", "St. Louis"), 139: ("TBR", "Tampa Bay"),
    140: ("TEX", "Texas"), 141: ("TOR", "Toronto"), 142: ("MIN", "Minnesota"),
    143: ("PHI", "Philadelphia"), 144: ("ATL", "Atlanta"), 145: ("CHW", "Chicago"),
    146: ("MIA", "Miami"), 147: ("NYY", "New York"), 158: ("MIL", "Milwaukee"),
}


def get(url, **params):
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=25)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2:
                print(f"  ! failed {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))


def fetch_standings():
    """One call: records, runs scored, runs allowed for all 30 clubs."""
    data = get(f"{MLB}/standings", leagueId="103,104", season=SEASON, standingsTypes="regularSeason")
    out = {}
    if not data:
        return out
    for div in data.get("records", []):
        for tr in div.get("teamRecords", []):
            tid = tr["team"]["id"]
            out[tid] = {
                "wins": tr.get("wins", 0),
                "losses": tr.get("losses", 0),
                "games": tr.get("wins", 0) + tr.get("losses", 0),
                "runs_scored": float(tr.get("runsScored") or 0),
                "runs_allowed": float(tr.get("runsAllowed") or 0),
            }
    return out


def ip_to_float(ip):
    """MLB reports innings as 145.2 meaning 145 and 2/3."""
    try:
        s = str(ip)
        whole, _, frac = s.partition(".")
        return int(whole) + (int(frac) / 3 if frac else 0.0)
    except Exception:
        return 0.0


def fetch_team_pitching(tid):
    data = get(f"{MLB}/teams/{tid}/stats", stats="season", group="pitching",
               season=SEASON, sportId=1, gameType="R")
    try:
        st = data["stats"][0]["splits"][0]["stat"]
        ip = ip_to_float(st.get("inningsPitched", 0))
        era = float(st.get("era") or 4.10)
        # Bullpen proxy: relievers throw ~42% of innings and run slightly
        # better than the staff line in the modern game.
        bp_ip = ip * 0.42
        return {"bullpen_ip": round(bp_ip, 1),
                "bullpen_er": round(bp_ip / 9 * era * 0.97, 1)}
    except Exception:
        return {"bullpen_ip": 400.0, "bullpen_er": 182.0}


def fetch_pitcher(pid, name):
    blank = {"name": name, "ip": 0.0, "hr": 0, "bb": 0, "hbp": 0, "so": 0}
    if not pid:
        return blank
    data = get(f"{MLB}/people/{pid}/stats", stats="season", group="pitching", season=SEASON)
    try:
        st = data["stats"][0]["splits"][0]["stat"]
        return {
            "name": name,
            "ip": round(ip_to_float(st.get("inningsPitched", 0)), 1),
            "hr": int(st.get("homeRuns") or 0),
            "bb": int(st.get("baseOnBalls") or 0),
            "hbp": int(st.get("hitByPitch") or 0),
            "so": int(st.get("strikeOuts") or 0),
        }
    except Exception:
        return blank


def fetch_odds(key):
    if not key:
        return []
    data = get(ODDS, apiKey=key, regions="us", markets="h2h,spreads,totals",
               oddsFormat="american", dateFormat="iso")
    return data or []


def pick_book(event, market_key):
    """First book offering a complete two-way market."""
    for bm in event.get("bookmakers", []):
        for m in bm.get("markets", []):
            if m["key"] == market_key and len(m.get("outcomes", [])) >= 2:
                return bm.get("title", "")[:3].upper(), m["outcomes"]
    return None, None


def match_event(events, home_full, away_full):
    for e in events:
        if e.get("home_team") == home_full and e.get("away_team") == away_full:
            return e
    # loose fallback on last word (city/nickname drift)
    hk, ak = home_full.split()[-1], away_full.split()[-1]
    for e in events:
        if hk in e.get("home_team", "") and ak in e.get("away_team", ""):
            return e
    return None


def build_markets(event, home_full, away_full):
    if not event:
        return None
    out = {}

    bk, oc = pick_book(event, "h2h")
    if not oc:
        return None
    price = {o["name"]: int(o["price"]) for o in oc}
    if home_full not in price or away_full not in price:
        return None
    out["ml"] = {"home": price[home_full], "away": price[away_full], "book": bk}

    bk, oc = pick_book(event, "spreads")
    if oc:
        by = {o["name"]: o for o in oc}
        h, a = by.get(home_full), by.get(away_full)
        if h and a:
            home_fav = float(h.get("point", 0)) < 0
            fav, dog = (h, a) if home_fav else (a, h)
            out["rl"] = {"line": 1.5, "home_fav": home_fav,
                         "fav": int(fav["price"]), "dog": int(dog["price"]), "book": bk}
    if "rl" not in out:
        out["rl"] = {"line": 1.5, "home_fav": price[home_full] < price[away_full],
                     "fav": -120, "dog": +100, "book": ""}

    bk, oc = pick_book(event, "totals")
    if oc:
        by = {o["name"]: o for o in oc}
        ov, un = by.get("Over"), by.get("Under")
        if ov and un:
            out["tot"] = {"line": float(ov.get("point", 8.5)),
                          "over": int(ov["price"]), "under": int(un["price"]), "book": bk}
    if "tot" not in out:
        out["tot"] = {"line": 8.5, "over": -110, "under": -110, "book": ""}

    return out


def main():
    key = os.environ.get("ODDS_API_KEY", "").strip()
    today = dt.date.today().isoformat()
    print(f"building slate for {today}")

    sched = get(f"{MLB}/schedule", sportId=1, date=today,
                hydrate="probablePitcher,team,linescore")
    if not sched or not sched.get("dates"):
        print("no games scheduled")
        json.dump({"date": today, "source": "statsapi.mlb.com", "games": []},
                  open("slate.json", "w"), indent=2)
        return

    standings = fetch_standings()
    events = fetch_odds(key)
    print(f"  {len(events)} odds events" if key else "  no odds key -> projections only")

    pitching_cache = {}
    games, skipped = [], 0

    for g in sched["dates"][0].get("games", []):
        if g.get("status", {}).get("abstractGameCode") == "F":
            continue

        h = g["teams"]["home"]["team"]
        a = g["teams"]["away"]["team"]
        hid, aid = h["id"], a["id"]
        if hid not in TEAMS or aid not in TEAMS:
            continue

        h_abbr, h_short = TEAMS[hid]
        a_abbr, a_short = TEAMS[aid]

        def team_block(tid, abbr, short):
            if tid not in pitching_cache:
                pitching_cache[tid] = fetch_team_pitching(tid)
                time.sleep(0.15)
            rec = standings.get(tid, {"wins": 0, "losses": 0, "games": 1,
                                      "runs_scored": 0, "runs_allowed": 0})
            return {"name": short, "abbr": abbr, **rec,
                    **pitching_cache[tid], "park_factor": PARK.get(abbr, 1.00)}

        hp = g["teams"]["home"].get("probablePitcher") or {}
        ap = g["teams"]["away"].get("probablePitcher") or {}
        h_sp = fetch_pitcher(hp.get("id"), hp.get("fullName", "TBD"))
        a_sp = fetch_pitcher(ap.get("id"), ap.get("fullName", "TBD"))
        time.sleep(0.15)

        markets = build_markets(match_event(events, h["name"], a["name"]),
                                h["name"], a["name"])
        if markets is None:
            markets = {"ml": {"home": -110, "away": -110, "book": ""},
                       "rl": {"line": 1.5, "home_fav": True, "fav": -120, "dog": 100, "book": ""},
                       "tot": {"line": 8.5, "over": -110, "under": -110, "book": ""}}
            skipped += 1

        try:
            when = dt.datetime.fromisoformat(g["gameDate"].replace("Z", "+00:00"))
            local = when - dt.timedelta(hours=4)  # ET
            stamp = local.strftime("%a %m/%d %-I:%M %p").upper()
        except Exception:
            stamp = today

        games.append({
            "time": stamp,
            "code": f"{a_abbr} @ {h_abbr}",
            "away": {"team": team_block(aid, a_abbr, a_short), "starter": a_sp},
            "home": {"team": team_block(hid, h_abbr, h_short), "starter": h_sp},
            "markets": markets,
        })

    payload = {
        "date": today,
        "source": "statsapi.mlb.com" + (" + the-odds-api.com" if key else ""),
        "has_odds": bool(key) and skipped < len(games),
        "games": games,
    }
    with open("slate.json", "w") as f:
        json.dump(payload, f, indent=2)

    print(f"  wrote slate.json: {len(games)} games"
          + (f", {skipped} without odds" if skipped else ""))


if __name__ == "__main__":
    main()
