"""Renders evaluated slate output to a standalone HTML dashboard."""

CSS = """
:root{--ground:#12161E;--panel:#1A1F29;--panel2:#212734;--rule:#2B3240;--rule2:#242A35;
--bone:#EAE7DE;--dim:#98A0AD;--faint:#69707E;--pos:#4FB79A;--posdeep:#1D5748;
--neg:#C9705A;--negdeep:#632E22;--warn:#D8A548;--warndeep:#46330F;--focus:#7FA8D9}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{background:var(--ground);color:var(--bone);font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:30px 20px 70px}
.mast{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--rule);padding-bottom:16px}
h1{font-family:"IBM Plex Sans Condensed",sans-serif;font-weight:700;font-size:29px;letter-spacing:-.01em;margin:0;line-height:1}
h1 span{color:var(--faint);font-weight:400}
.meta{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--dim);text-align:right;line-height:1.75}
.notice{margin:18px 0 24px;border:1px solid var(--warndeep);background:rgba(216,165,72,.06);border-radius:6px;padding:13px 15px;font-size:13.5px;color:var(--dim);display:flex;gap:11px}
.notice b{color:var(--warn);font-weight:500}
.notice i{font-style:normal;font-family:"IBM Plex Mono",monospace;color:var(--warn);flex:none}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:8px;margin-top:16px;overflow:hidden}
.head{display:flex;align-items:center;gap:12px;padding:10px 16px;border-bottom:1px solid var(--rule2);background:var(--panel2)}
.t{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--dim)}
.c{font-family:"IBM Plex Sans Condensed",sans-serif;font-weight:600;font-size:13px;letter-spacing:.11em;color:var(--faint)}
.body{display:grid;grid-template-columns:minmax(0,246px) minmax(0,1fr)}
@media(max-width:820px){.body{grid-template-columns:1fr}}
.proj{padding:15px 16px;border-right:1px solid var(--rule2)}
@media(max-width:820px){.proj{border-right:none;border-bottom:1px solid var(--rule2)}}
.lbl{font-family:"IBM Plex Mono",monospace;font-size:9.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--faint);margin-bottom:9px}
.tr{display:flex;align-items:baseline;justify-content:space-between;gap:10px;padding:6px 0}
.tr+.tr{border-top:1px solid var(--rule2)}
.tn{font-family:"IBM Plex Sans Condensed",sans-serif;font-weight:600;font-size:16px}
.tn u{text-decoration:none;font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--faint);font-weight:400;margin-left:6px}
.tv{font-family:"IBM Plex Mono",monospace;font-weight:500;font-size:24px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.sp{margin-top:10px;font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--faint);line-height:1.75}
.mkts{display:flex;flex-direction:column}
.m{display:grid;grid-template-columns:66px minmax(0,1fr) 88px 74px 96px;gap:12px;align-items:center;padding:11px 16px}
.m+.m{border-top:1px solid var(--rule2)}
@media(max-width:820px){.m{grid-template-columns:64px minmax(0,1fr) 80px;row-gap:7px}.m .pr{grid-column:2/4;text-align:left}.m .st{display:none}}
.mn{font-family:"IBM Plex Sans Condensed",sans-serif;font-weight:600;font-size:12.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--dim)}
.pk{font-family:"IBM Plex Mono",monospace;font-size:13px;margin-bottom:6px}
.pk em{font-style:normal;color:var(--faint)}
.bar{position:relative;height:8px;background:var(--panel2);border-radius:2px;overflow:hidden}
.bg{position:absolute;left:0;top:0;bottom:0;border-radius:2px}
.bf{position:absolute;top:0;bottom:0;background-image:repeating-linear-gradient(115deg,rgba(234,231,222,.3) 0 2px,transparent 2px 5px)}
.sc{display:flex;justify-content:space-between;font-family:"IBM Plex Mono",monospace;font-size:9.5px;color:var(--faint);margin-top:4px}
.ev{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:18px;text-align:right;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.ev u{display:block;text-decoration:none;font-size:9.5px;font-weight:400;letter-spacing:.07em;text-transform:uppercase;color:var(--faint)}
.st{text-align:center;font-size:11px;letter-spacing:.09em;color:var(--warn);font-family:"IBM Plex Mono",monospace}
.st u{display:block;text-decoration:none;font-size:9.5px;color:var(--faint);letter-spacing:.07em;text-transform:uppercase;margin-top:1px}
.pr{text-align:right;font-family:"IBM Plex Mono",monospace;font-size:13px;font-variant-numeric:tabular-nums}
.pr u{display:block;text-decoration:none;font-size:9.5px;color:var(--faint);letter-spacing:.07em;text-transform:uppercase}
.bk{display:inline-block;font-size:9.5px;letter-spacing:.06em;background:var(--panel2);border:1px solid var(--rule);color:var(--dim);padding:1px 5px;border-radius:3px;margin-left:5px}
.fl{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:9px;letter-spacing:.08em;text-transform:uppercase;padding:2px 6px;border-radius:3px;margin-left:6px;background:var(--warndeep);color:var(--warn)}
.pass{background:#282E38;color:var(--faint)}
footer{margin-top:38px;padding-top:18px;border-top:1px solid var(--rule);font-size:13px;color:var(--faint);line-height:1.8}
footer code{font-family:"IBM Plex Mono",monospace;color:var(--dim);background:var(--panel2);padding:1px 5px;border-radius:3px;font-size:12px}
"""


def bar_html(r):
    scale = 0.15
    gross = min(abs(r["gross"]) / scale, 1) * 100
    fee = min(abs(r["drag"]) / scale, 1) * 100
    solid = max(gross - fee, 0)
    good = r["ev"] >= 0
    col = "var(--pos)" if good else "var(--neg)"
    deep = "var(--posdeep)" if good else "var(--negdeep)"
    return (f'<div class="bar"><span class="bg" style="width:{gross:.1f}%;background:{deep}"></span>'
            f'<span class="bg" style="width:{solid:.1f}%;background:{col}"></span>'
            f'<span class="bf" style="left:{solid:.1f}%;width:{min(fee,gross):.1f}%"></span></div>'
            f'<div class="sc"><span>model {r["p"]*100:.1f}% \u00b7 market {r["mkt"]*100:.1f}%</span>'
            f'<span>drag \u2212{r["drag"]*100:.2f}pp</span></div>')


def row_html(r):
    good = r["ev"] >= 0
    suspect = r.get("suspect")
    col = "var(--warn)" if suspect else ("var(--pos)" if good else "var(--neg)")
    if suspect:
        flag = '<span class="fl">implausible \u2014 check line</span>'
    elif not good:
        flag = '<span class="fl pass">pass</span>'
    else:
        flag = ''
    book = f'<span class="bk">{r["book"]}</span>' if r["book"] else '<span class="bk">no book</span>'
    stake = f'{r["stake"]*100:.2f}%' if r["stake"] > 0 else '\u2014'
    return f"""<div class="m">
  <span class="mn">{r['label']}</span>
  <div><div class="pk">{r['pick']}{flag}</div>{bar_html(r)}</div>
  <div class="ev" style="color:{col}">{'+' if good else ''}{r['ev']*100:.1f}%<u>net ev</u></div>
  <div class="st">{'\u2605'*r['stars']}{'\u2606'*(5-r['stars'])}<u>rating</u></div>
  <div class="pr">{r['price_label']}{book}<u>{stake} stake</u></div>
</div>"""


def card_html(g):
    thin = min(g["away"]["ip"], g["home"]["ip"]) < 40
    flag = '<span class="fl">thin starter</span>' if thin else ''
    if g.get("unpriced"):
        flag += '<span class="fl">no odds \u2014 projection only</span>'
    return f"""<div class="card">
  <div class="head"><span class="t">{g['time']}</span><span class="c">{g['code']}</span>{flag}</div>
  <div class="body">
    <div class="proj">
      <div class="lbl">Projected runs</div>
      <div class="tr"><span class="tn">{g['away']['name']}<u>{g['away']['rec']}</u></span>
        <span class="tv">{g['away']['mu']:.1f}</span></div>
      <div class="tr"><span class="tn">{g['home']['name']}<u>{g['home']['rec']}</u></span>
        <span class="tv">{g['home']['mu']:.1f}</span></div>
      <div class="sp">{g['home']['sp']} ({g['home']['ip']:.0f} ip)<br>
        {g['away']['sp']} ({g['away']['ip']:.0f} ip)<br>
        home win {g['home_win']*100:.1f}% \u00b7 pythag exp {g['pythag_exp']}</div>
    </div>
    <div class="mkts">{''.join(row_html(r) for r in g['rows'])}</div>
  </div>
</div>"""


def write_dashboard(games, path, date="2026-07-28", updated="", has_odds=True):
    plays = [r for g in games for r in g["rows"] if r["ev"] > 0]
    best = max((r["ev"] for g in games for r in g["rows"]), default=0)
    banner = ("<b>Placeholder inputs &mdash; not validated.</b> Stat lines are synthetic."
              if not has_odds else
              "<b>Live data, unvalidated model.</b> Stats and odds are real; the model has not been "
              "walk-forward tested, so no edge below is verified.")
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Slate \u2014 {date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<header class="mast"><h1>Slate <span>/ mlb</span></h1>
<div class="meta">{date} \u00b7 {len(games)} games \u00b7 {len(plays)} positive-ev plays<br>best {best*100:+.1f}% \u00b7 updated {updated}</div></header>
<div class="notice"><i>!</i><div>{banner}</div></div>
{''.join(card_html(g) for g in games)}
<footer>
<p>Runs projected by odds-ratio expectancy: league RPG scaled by regressed team offense, regressed staff RA9 (FIP for starters at a 70-IP crossover, blended 58/42 with bullpen), park factor, and home-field. Scoring is Negative Binomial with k=4.2, convolved independently across both sides; ties resolve 52/48 to the home club for extra innings.</p>
<p>Market probabilities are power-devigged from the two-way price. The hatched span on each bar is the portion of gross edge consumed by hold; only the solid remainder is real. Ratings measure dampened edge against model uncertainty, so a thin-sample starter rates below an equivalent edge from a settled projection \u2014 the rating is not a restatement of EV. Stakes are quarter-Kelly, capped at 2% of bankroll.</p>
</footer></div></body></html>"""
    with open(path, "w") as f:
        f.write(html)
