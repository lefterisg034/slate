"""Runs the model over slate.json and writes index.html for publishing."""

import datetime as dt
import json

from mlb_model import run_slate
from render import write_dashboard

with open("slate.json") as f:
    meta = json.load(f)

games = run_slate("slate.json", venue="book", frac=0.25)
stamp = dt.datetime.now(dt.timezone.utc).strftime("%H:%M UTC")

write_dashboard(games, "index.html",
                date=meta.get("date", ""),
                updated=stamp,
                has_odds=meta.get("has_odds", False))

plays = sum(1 for g in games for r in g["rows"] if r["ev"] > 0)
print(f"built index.html: {len(games)} games, {plays} positive-ev plays")

for g in games:
    if not g["rows"]:
        continue
    b = max(g["rows"], key=lambda r: r["ev"])
    print(f"  {g['code']:<12} {g['away']['mu']:.2f}-{g['home']['mu']:.2f}  "
          f"{b['label']:<7} {b['ev']*100:+6.1f}%")
