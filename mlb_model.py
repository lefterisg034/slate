"""
MLB slate projection + EV engine.

Design principle: every parameter here is either (a) theoretically derived,
(b) a published stabilization point from public sabermetric research, or
(c) exposed as a config knob. Nothing is grid-searched against 2026 results,
because in-sample optimization on a partial season degrades out-of-sample
accuracy -- which is the only accuracy that pays.

Pipeline:
  slate.json -> project runs -> Negative Binomial convolution -> market probs
  -> devig -> fee-adjusted EV -> fractional Kelly -> dashboard.html
"""

import json
import math
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# League constants. Update once per season from public leaderboards.
# ---------------------------------------------------------------------------

LG = {
    "runs_per_game": 4.45,     # per team
    "fip_constant": 3.15,      # cFIP, recomputed yearly
    "era": 4.10,
    "hfa_run_mult": 1.021,     # modern HFA ~52.8% win rate, shrinking
    "starter_share": 0.58,     # ~5.2 IP of 9; matches league IP splits
    "nb_dispersion": 4.2,      # k from mu^2/(var-mu); MLB var ~9.3, mu ~4.45
}

# Stabilization points (regression weights), in the units of the stat.
# These come from published reliability work, not from this season's data.
STABILIZE = {
    "team_runs_games": 45,     # team offense regresses toward league mean
    "pitcher_fip_ip": 70,      # FIP reliability crossover
    "bullpen_ip": 110,
}

MAX_RUNS = 26


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

@dataclass
class Team:
    name: str
    abbr: str
    wins: int
    losses: int
    games: int
    runs_scored: float          # season total
    runs_allowed: float
    bullpen_ip: float
    bullpen_er: float
    park_factor: float = 1.00   # home park, runs multiplier


@dataclass
class Pitcher:
    name: str
    ip: float
    hr: int
    bb: int
    hbp: int
    so: int

    def raw_fip(self) -> float:
        if self.ip <= 0:
            return LG["era"]
        return (13 * self.hr + 3 * (self.bb + self.hbp) - 2 * self.so) / self.ip + LG["fip_constant"]

    def projected_ra9(self) -> float:
        """FIP regressed to league mean by innings pitched."""
        w = self.ip / (self.ip + STABILIZE["pitcher_fip_ip"])
        return w * self.raw_fip() + (1 - w) * LG["era"]

    def confidence(self) -> float:
        """0..1 -- how much we trust this projection. Drives edge dampening."""
        return min(1.0, self.ip / STABILIZE["pitcher_fip_ip"])


def regress(observed: float, league: float, sample: float, stabilizer: float) -> float:
    w = sample / (sample + stabilizer)
    return w * observed + (1 - w) * league


def team_offense(t: Team) -> float:
    """Regressed runs scored per game, as a ratio to league average."""
    rpg = t.runs_scored / max(t.games, 1)
    reg = regress(rpg, LG["runs_per_game"], t.games, STABILIZE["team_runs_games"])
    return reg / LG["runs_per_game"]


def staff_ra9(starter: Pitcher, t: Team) -> float:
    """Blend regressed starter FIP with regressed bullpen ERA."""
    bp_era = (t.bullpen_er * 9 / t.bullpen_ip) if t.bullpen_ip > 0 else LG["era"]
    bp = regress(bp_era, LG["era"], t.bullpen_ip, STABILIZE["bullpen_ip"])
    s = LG["starter_share"]
    return s * starter.projected_ra9() + (1 - s) * bp


def project_runs(off_team: Team, def_team: Team, def_starter: Pitcher,
                 park: float, is_home: bool) -> float:
    """
    Odds-ratio (log5-style) run expectancy:
        E = lg * (offense ratio) * (defense ratio) * park * hfa
    This form is standard and validates well out of sample.
    """
    off = team_offense(off_team)
    dfn = staff_ra9(def_starter, def_team) / LG["era"]
    e = LG["runs_per_game"] * off * dfn * park
    if is_home:
        e *= LG["hfa_run_mult"]
    return max(e, 1.2)


# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------

def nb_pmf(mu: float, k: float) -> list:
    p = k / (k + mu)
    out = [p ** k]
    for x in range(1, MAX_RUNS + 1):
        out.append(out[-1] * ((k + x - 1) / x) * (1 - p))
    s = sum(out)
    return [v / s for v in out]


@dataclass
class GameDist:
    home_win: float
    diff: dict = field(default_factory=dict)
    total: dict = field(default_factory=dict)


def convolve(mu_home: float, mu_away: float, k: float) -> GameDist:
    H, A = nb_pmf(mu_home, k), nb_pmf(mu_away, k)
    hw = tie = 0.0
    diff, total = {}, {}
    for h, ph in enumerate(H):
        if ph < 1e-11:
            continue
        for a, pa in enumerate(A):
            pr = ph * pa
            if pr < 1e-11:
                continue
            if h > a:
                hw += pr
            elif h == a:
                tie += pr
            diff[h - a] = diff.get(h - a, 0.0) + pr
            total[h + a] = total.get(h + a, 0.0) + pr
    # Extra innings: near coin-flip, slight home edge from walk-off structure
    return GameDist(hw + tie * 0.52, diff, total)


# ---------------------------------------------------------------------------
# Market math
# ---------------------------------------------------------------------------

def american_to_dec(o: int) -> float:
    return 1 + o / 100 if o > 0 else 1 + 100 / abs(o)


def american_to_imp(o: int) -> float:
    return 100 / (o + 100) if o > 0 else abs(o) / (abs(o) + 100)


def devig_power(q1: float, q2: float) -> tuple:
    """Power method -- handles favorite-longshot bias better than proportional."""
    lo, hi = 0.5, 3.0
    for _ in range(80):
        m = (lo + hi) / 2
        if q1 ** m + q2 ** m > 1:
            lo = m
        else:
            hi = m
    a = (lo + hi) / 2
    p1, p2 = q1 ** a, q2 ** a
    s = p1 + p2
    return p1 / s, p2 / s


def kalshi_fee(price: float, maker: bool = False) -> float:
    return 0.07 * price * (1 - price) * (0.25 if maker else 1.0)


def evaluate(p_model: float, p_market: float, american: int, venue: str) -> dict:
    if venue == "book":
        b = american_to_dec(american) - 1
        ev = p_model * b - (1 - p_model)
        drag = american_to_imp(american) - p_market
        label = f"{american:+d}"
    else:
        maker = venue == "kalshi_maker"
        P = min(max(p_market, 0.02), 0.98)
        fee = kalshi_fee(P, maker)
        cost = P + fee
        b = (1 - cost) / cost
        ev = (p_model - cost) / cost
        drag = fee
        label = f"{round(P * 100)}\u00a2 {'limit' if maker else 'mkt'}"
    return {"ev": ev, "b": b, "drag": drag, "gross": p_model - p_market, "price_label": label}


def kelly(p: float, b: float, frac: float, cap: float = 0.02) -> float:
    if b <= 0:
        return 0.0
    f = (p * b - (1 - p)) / b
    return max(0.0, min(f * frac, cap))


# ---------------------------------------------------------------------------
# Slate evaluation
# ---------------------------------------------------------------------------

def dampen(edge: float, confidence: float) -> float:
    """
    Shrink the edge toward zero when the starter projection is thin.
    A 20-IP rookie should not generate a full-strength signal.
    """
    return edge * (0.45 + 0.55 * confidence)


def stars(edge: float, confidence: float, sigma: float = 0.028) -> int:
    """
    Rating = dampened edge measured in units of model uncertainty.
    Deliberately NOT a restatement of EV: a big edge from a thin sample
    rates lower than a moderate edge from a well-established one.
    """
    z = abs(dampen(edge, confidence)) / sigma
    for i, t in enumerate([0.5, 1.0, 1.6, 2.3]):
        if z < t:
            return i + 1
    return 5


def eval_game(g: dict, venue: str, frac: float) -> dict:
    home = Team(**g["home"]["team"])
    away = Team(**g["away"]["team"])
    hp = Pitcher(**g["home"]["starter"])
    ap = Pitcher(**g["away"]["starter"])
    park = home.park_factor

    mu_home = project_runs(home, away, ap, park, is_home=True)
    mu_away = project_runs(away, home, hp, park, is_home=False)
    D = convolve(mu_home, mu_away, LG["nb_dispersion"])
    conf = min(hp.confidence(), ap.confidence())

    M = g["markets"]
    rows = []

    # Moneyline
    mh, ma = devig_power(american_to_imp(M["ml"]["home"]), american_to_imp(M["ml"]["away"]))
    if (D.home_win - mh) >= ((1 - D.home_win) - ma):
        p, mk, px, who = D.home_win, mh, M["ml"]["home"], home.name
    else:
        p, mk, px, who = 1 - D.home_win, ma, M["ml"]["away"], away.name
    rows.append({"label": "Money", "pick": f"{who} ML", "p": p, "mkt": mk,
                 "price": px, "book": M["ml"].get("book", "")})

    # Run line
    L = M["rl"]["line"]
    fav_home = M["rl"]["home_fav"]
    p_fav = sum(v for d, v in D.diff.items() if (d > L if fav_home else -d > L))
    mf, md = devig_power(american_to_imp(M["rl"]["fav"]), american_to_imp(M["rl"]["dog"]))
    fav_t, dog_t = (home.name, away.name) if fav_home else (away.name, home.name)
    if (p_fav - mf) >= ((1 - p_fav) - md):
        rows.append({"label": "Spread", "pick": f"{fav_t} \u22121\u00bd", "p": p_fav,
                     "mkt": mf, "price": M["rl"]["fav"], "book": M["rl"].get("book", "")})
    else:
        rows.append({"label": "Spread", "pick": f"{dog_t} +1\u00bd", "p": 1 - p_fav,
                     "mkt": md, "price": M["rl"]["dog"], "book": M["rl"].get("book", "")})

    # Total, with push handling on whole numbers
    TL = M["tot"]["line"]
    p_over = sum(v for t, v in D.total.items() if t > TL)
    p_push = sum(v for t, v in D.total.items() if t == TL)
    p_under = 1 - p_over - p_push
    live = 1 - p_push
    o_adj = p_over / live if live > 0 else 0
    u_adj = p_under / live if live > 0 else 0
    mo, mu_ = devig_power(american_to_imp(M["tot"]["over"]), american_to_imp(M["tot"]["under"]))
    push_note = f" \u00b7 push {p_push*100:.0f}%" if p_push > 0.005 else ""
    if (o_adj - mo) >= (u_adj - mu_):
        rows.append({"label": "Total", "pick": f"o{TL}{push_note}", "p": o_adj, "mkt": mo,
                     "price": M["tot"]["over"], "book": M["tot"].get("book", "")})
    else:
        rows.append({"label": "Total", "pick": f"u{TL}{push_note}", "p": u_adj, "mkt": mu_,
                     "price": M["tot"]["under"], "book": M["tot"].get("book", "")})

    out = []
    for r in rows:
        e = evaluate(r["p"], r["mkt"], r["price"], venue)
        damped = dampen(e["gross"], conf)
        out.append({**r, **e,
                    "damped": damped,
                    "stars": stars(e["gross"], conf),
                    "stake": kelly(r["mkt"] + damped, e["b"], frac)})

    rpg = mu_home + mu_away
    return {
        "time": g["time"], "code": g["code"],
        "away": {"name": away.name, "rec": f"{away.wins}-{away.losses}", "mu": mu_away,
                 "sp": ap.name, "ip": ap.ip},
        "home": {"name": home.name, "rec": f"{home.wins}-{home.losses}", "mu": mu_home,
                 "sp": hp.name, "ip": hp.ip},
        "home_win": D.home_win,
        "pythag_exp": round(rpg ** 0.287, 3),
        "confidence": conf,
        "rows": out,
    }


def run_slate(path: str, venue: str = "book", frac: float = 0.25) -> list:
    with open(path) as f:
        slate = json.load(f)
    return [eval_game(g, venue, frac) for g in slate["games"]]


if __name__ == "__main__":
    import sys
    from render import write_dashboard

    src = sys.argv[1] if len(sys.argv) > 1 else "slate.json"
    games = run_slate(src)
    write_dashboard(games, "dashboard.html")
    print(f"{len(games)} games projected -> dashboard.html")
    for g in games:
        best = max(g["rows"], key=lambda r: r["ev"])
        print(f"  {g['code']:<12} {g['away']['mu']:.2f}-{g['home']['mu']:.2f}  "
              f"best {best['label']:<7} {best['ev']*100:+6.1f}%  {'*' * best['stars']}")
