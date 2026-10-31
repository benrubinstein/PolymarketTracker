"""NBA, NFL and soccer Polymarket position dashboard.

Usage: py polymarket_tracker.py [YYYY-MM-DD]
Dependencies: requests
Outputs: polymarket_report.html, polymarket_positions.csv
Public position data is incomplete for some large accounts.
"""
import csv
import html
import re
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
import requests

TRADERS = {
    "BreakTheBank": "0xf0318c32136c2db7fec88b84869aee6a1106c80c",
    "joseph00677": "0xcdcccd0f2d86e450d973da415ad2430e5cc7935a",
    "UpTheBlues": "0x2a69660046d7acc4ab204d7cc5ba78b0776cd2f7",
    "HomeRunHazard": "0x5268527977f700f9bf9b6d5cd843859e4e70135d",
    "Flaznorp": "0x821dab0565ebf5b327f51db06223fdcfe01acf16",
    "theowalcott": "0x7ad71d79a3bb90d0a87a06500fa0fe11663842aa",
    "gmpm2": "0x67542c3219b37fd1610aad290676ff91cdbfe3bc",
    "Diabolical-Prize": "0x7c37b52eb226bcb9411375ec48b0169663fb6aeb",
    "monkeymashingkeyboard": "0x684baa57c338c2549aec0aa3f034f695d72a8409",
    "takeormake": "0xa38a455bbdd4b68486548b7e19da99903f4f821d",
    "juice-fruit": "0x5fdd66ffd0325d4e8d1d86fbec50caa31770a747",
    "Jsram": "0x83720820a8aa6c3f20ad71850e7a1a17d16c5223",
    "RN1": "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
    "ArielFilipino": "0xe18ecc345e00ee7c4f2d1f676f3dd2acb112f826",
    "keeptheblueflagflyinghigh": "0x0d6a1ada6d7ff785ab4b7263d9ce8e2baa85aa98",
    "BillyGating": "0x2dfa4e79eca44b7c774f40a45535adbc368a6f60"
}

DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-31"
PAGE_SIZE = 500
MAX_PAGES = 40
MIN_SHARES = 1.0
API = "https://data-api.polymarket.com/positions"
CSV_FILE = "polymarket_positions.csv"
HTML_FILE = "polymarket_report.html"
ACTIVITY_API = "https://data-api.polymarket.com/activity"
SOCCER = {"epl", "bun", "lal", "sea", "lig", "ucl", "uel", "uecl", "mls",
          "ered", "rus", "por", "sco", "bra", "arg", "mex", "tur", "bel",
          "fra", "esp", "ita", "ger", "eng", "ned", "sau", "wc", "cwc"}

def number(value):
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0.0

def sport_of(p):
    slug = str(p.get("eventSlug") or p.get("slug") or "").lower()
    prefix = slug.split("-", 1)[0]
    if prefix == "nba":
        return "NBA"
    if prefix == "nfl":
        return "NFL"
    if prefix in SOCCER:
        return "SOCCER"
    return None

def is_target(p):
    slug = str(p.get("eventSlug") or p.get("slug") or "")
    return bool(re.search(r"(?<!\d)" + re.escape(DATE) + r"(?!\d)", slug))

def fetch_positions(session, name, wallet):
    positions = []
    complete = False
    for page in range(MAX_PAGES):
        try:
            r = session.get(API, params={
                "user": wallet, "limit": PAGE_SIZE,
                "offset": page * PAGE_SIZE, "sizeThreshold": 0
            }, timeout=35)
            r.raise_for_status()
            batch = r.json()
            if not isinstance(batch, list):
                raise ValueError("Unexpected API response")
        except (requests.RequestException, ValueError) as exc:
            print(f"  API error: {exc}", flush=True)
            break
        positions.extend(batch)
        if len(batch) < PAGE_SIZE:
            complete = True
            break
        time.sleep(0.10)
    print(f"  {len(positions)} positions; complete={complete}", flush=True)
    return positions, complete

def market_type(title):
    t = title.lower()
    if "spread:" in t:
        return "Spread"
    if "o/u" in t or "over/under" in t or "total goals" in t:
        return "Total"
    if "halftime" in t or "half-time" in t:
        return "Halftime"
    if t.startswith("will "):
        return "Yes/No proposition"
    if " vs." in t or " vs " in t:
        return "Match winner / other"
    return "Other"

def recent_activity(session, wallet):
    try:
        r = session.get(ACTIVITY_API, params={"user": wallet, "type": "TRADE", "limit": 500}, timeout=25)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except (requests.RequestException, ValueError):
        return []

def build():
    date.fromisoformat(DATE)
    session = requests.Session()
    # Aggregate multiple position records by condition, trader and outcome.
    holdings = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        "shares": 0.0, "current_value": 0.0, "initial_value": 0.0,
        "has_current": False, "has_initial": False,
        "price_weight": 0.0, "price_shares": 0.0
    })))
    meta = {}
    partial = set()
    scanned = {}
    activity = defaultdict(lambda: defaultdict(lambda: {"buys": 0, "sells": 0, "buy_usd": 0.0, "sell_usd": 0.0}))
    for name, wallet in TRADERS.items():
        print(f"Checking {name}...", flush=True)
        positions, complete = fetch_positions(session, name, wallet)
        scanned[name] = len(positions)
        for trade in recent_activity(session, wallet):
            cid = trade.get("conditionId")
            side = str(trade.get("side") or "").upper()
            if not cid or side not in ("BUY", "SELL"):
                continue
            dollars = number(trade.get("usdcSize")) or number(trade.get("size")) * number(trade.get("price"))
            key = "buys" if side == "BUY" else "sells"
            usd_key = "buy_usd" if side == "BUY" else "sell_usd"
            activity[cid][name][key] += 1
            activity[cid][name][usd_key] += dollars
        if not complete:
            partial.add(name)
        for p in positions:
            sport = sport_of(p)
            if not sport or not is_target(p):
                continue
            cid = p.get("conditionId")
            outcome = p.get("outcome")
            shares = number(p.get("size"))
            if not cid or outcome is None or shares <= 0:
                continue
            outcome = str(outcome)
            h = holdings[cid][name][outcome]
            h["shares"] += shares
            if p.get("currentValue") is not None:
                h["current_value"] += number(p["currentValue"])
                h["has_current"] = True
            if p.get("initialValue") is not None:
                h["initial_value"] += number(p["initialValue"])
                h["has_initial"] = True
            if p.get("curPrice") is not None:
                price = number(p["curPrice"])
                if 0 <= price <= 1:
                    h["price_weight"] += shares * price
                    h["price_shares"] += shares
            meta.setdefault(cid, {
                "sport": sport, "market": str(p.get("title") or "Unknown market"),
                "slug": str(p.get("eventSlug") or p.get("slug") or "")
            })

    rows = []
    for cid, traders in holdings.items():
        outcomes = sorted({outcome for sides in traders.values() for outcome in sides})
        if len(outcomes) > 2 or not outcomes:
            continue
        by_side = defaultdict(list)
        for name, sides in traders.items():
            # Subtract shares for binary markets; missing opposing positions remain unknown.
            if len(outcomes) == 2:
                a, b = outcomes
                delta = sides[a]["shares"] - sides[b]["shares"]
                if abs(delta) < MIN_SHARES:
                    continue
                winning = a if delta > 0 else b
                net_shares = abs(delta)
            else:
                winning = outcomes[0]
                net_shares = sides[winning]["shares"]
                if net_shares < MIN_SHARES:
                    continue
            data = sides[winning]
            by_side[winning].append({
                "name": name, "shares": net_shares,
                "value": data["current_value"] if data["has_current"] else None,
                "cost": data["initial_value"] if data["has_initial"] else None,
                "price": (data["price_weight"] / data["price_shares"])
                         if data["price_shares"] else None,
                "partial": name in partial,
                "activity": activity[cid][name]
            })
        for outcome, supporters in by_side.items():
            info = meta[cid]
            prices = [s["price"] for s in supporters if s["price"] is not None]
            values = [s["value"] for s in supporters if s["value"] is not None]
            costs = [s["cost"] for s in supporters if s["cost"] is not None]
            warnings = []
            total_shares = sum(s["shares"] for s in supporters)
            largest_pct = 100 * max(s["shares"] for s in supporters) / total_shares if total_shares else 0
            biggest = max(s["shares"] for s in supporters)
            meaningful = sum(s["shares"] >= biggest * 0.1 for s in supporters)
            sample_buys = sum(s["activity"]["buys"] for s in supporters)
            sample_sells = sum(s["activity"]["sells"] for s in supporters)
            if len(supporters) >= 2 and largest_pct >= 90:
                warnings.append("One trader dominates observed shares")
            if any(s["partial"] for s in supporters):
                warnings.append("Incomplete trader scan")
            if len(outcomes) == 1:
                warnings.append("Opposing side not observed")
            if not warnings:
                warnings.append("Both sides observed")
            if len(prices) != len(supporters):
                warnings.append("Some prices unavailable")
            if len(values) != len(supporters):
                warnings.append("Some values unavailable")
            rows.append({
                "sport": info["sport"], "market": info["market"],
                "market_type": market_type(info["market"]),
                "largest_trader_pct": round(largest_pct, 1),
                "meaningful_traders": meaningful,
                "recent_sample_buys": sample_buys,
                "recent_sample_sells": sample_sells,
                "outcome": outcome, "traders": len(supporters),
                "net_shares": round(sum(s["shares"] for s in supporters), 2),
                "observed_value_usd": round(sum(values), 2) if values else "",
                "value_coverage": f"{len(values)}/{len(supporters)}",
                "observed_cost_usd": round(sum(costs), 2) if costs else "",
                "price_snapshot": round(sum(prices) / len(prices), 4) if prices else "",
                "price_coverage": f"{len(prices)}/{len(supporters)}",
                "supporters": "; ".join(
                    f"{s['name']} ({s['shares']:,.0f} net shares"
                    + (f", ${s['value']:,.2f} current outcome value" if s["value"] is not None else "")
                    + ")" for s in sorted(supporters, key=lambda x: -x["shares"])
                ),
                "quality": "; ".join(warnings),
                "event_url": "https://polymarket.com/event/" + info["slug"],
                "condition_id": cid,
            })
    order = {"NBA": 0, "NFL": 1, "SOCCER": 2}
    rows.sort(key=lambda r: (order[r["sport"]], -r["traders"], -r["net_shares"]))
    return rows, partial, scanned

def save_csv(rows):
    fields = ["sport", "market", "market_type", "outcome", "traders", "largest_trader_pct", "meaningful_traders", "recent_sample_buys", "recent_sample_sells", "net_shares",
              "observed_value_usd", "value_coverage", "observed_cost_usd",
              "price_snapshot", "price_coverage", "supporters", "quality",
              "event_url", "condition_id"]
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def render(rows, partial, scanned):
    esc = lambda x: html.escape(str(x), quote=True)
    blocks = []
    for sport in ("NBA", "NFL", "SOCCER"):
        subset = [r for r in rows if r["sport"] == sport]
        consensus = [r for r in subset if r["traders"] >= 2]
        singles = [r for r in subset if r["traders"] == 1]
        blocks.append(f"<section><h2>{sport} · {len(consensus)} consensus / {len(singles)} singles</h2>")
        for label, group in (("Consensus (2+)", consensus), ("Single-trader positions", singles)):
            blocks.append(f"<h3>{label}</h3>")
            if not group:
                blocks.append("<p class='muted'>No qualifying positions observed.</p>")
            for r in group:
                price = f"{float(r['price_snapshot'])*100:.1f}%" if r["price_snapshot"] != "" else "N/A"
                value = f"${float(r['observed_value_usd']):,.2f}" if r["observed_value_usd"] != "" else "N/A"
                cost = f"${float(r['observed_cost_usd']):,.2f}" if r["observed_cost_usd"] != "" else "N/A"
                blocks.append(
                    "<article data-sport='" + esc(r["sport"]) + "' data-count='" + esc(r["traders"]) + "' data-shares='" + esc(r["net_shares"]) + "'><p class='muted'>" + esc(r["market_type"]) + " · " + esc(r["meaningful_traders"]) + " meaningful trader(s) · Largest " + esc(r["largest_trader_pct"]) + "% · Sampled buys/sells: " + esc(r["recent_sample_buys"]) + "/" + esc(r["recent_sample_sells"]) + "</p><div class='top'><strong>" + esc(r["market"]) +
                    "</strong><span class='pill'>" + esc(r["traders"]) + " trader(s)</span></div>" +
                    "<div class='outcome'>" + esc(r["outcome"]) + "</div>" +
                    "<div class='metrics'><div>Net shares<b>" + esc(r["net_shares"]) +
                    "</b></div><div>Observed value<b>" + esc(value) +
                    "</b><small>Coverage " + esc(r["value_coverage"]) +
                    "</small></div><div>Observed cost<b>" + esc(cost) +
                    "</b></div><div>Position price snapshot<b>" + esc(price) +
                    "</b><small>Coverage " + esc(r["price_coverage"]) +
                    "</small></div></div><p>" + esc(r["supporters"]) +
                    "</p><p class='warning'>" + esc(r["quality"]) +
                    "</p><a href='" + esc(r["event_url"]) +
                    "' target='_blank' rel='noopener noreferrer'>Open Polymarket event</a></article>"
                )
        blocks.append("</section>")
    body = "\n".join(blocks)
    doc = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Polymarket Sports Tracker</title>
<style>
:root{font-family:system-ui,Segoe UI,sans-serif;color:#e8edf8;background:#0b1220}
body{max-width:1100px;margin:auto;padding:28px 18px 60px}
h1{font-size:2rem;margin-bottom:6px}h2{margin-top:40px;border-bottom:1px solid #34435d;padding-bottom:12px}
h3{color:#a9b9d4}p{line-height:1.55}.muted{color:#9baac1}
section{margin-top:30px}article{background:#152138;border:1px solid #293a58;border-radius:14px;padding:18px;margin:12px 0}
.top{display:flex;justify-content:space-between;gap:12px;align-items:center}
.pill{background:#294469;padding:5px 10px;border-radius:50px;white-space:nowrap}
.outcome{font-size:1.2rem;font-weight:700;color:#8fd3ff;margin:10px 0}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin:16px 0}
.metrics div{background:#0d192b;padding:12px;border-radius:9px;color:#9fb2cf;font-size:.83rem}
.metrics b{display:block;font-size:1.15rem;color:white;margin-top:4px}
.metrics small{display:block;margin-top:4px}
.warning{color:#f2ca8a}a{color:#7cbcff}
.notice{padding:15px;background:#1b2941;border-radius:12px;border-left:3px solid #89b6ff}
</style></head><body>"""
    doc += f"<h1>Polymarket Sports Tracker</h1><p class='muted'>Event date: {esc(DATE)} · NBA / NFL / Soccer</p>"
    doc += "<div class='notice'><b>Interpretation:</b> This is a position-overlap monitor, not a recommendation or performance forecast. Dollar values and prices are position API snapshots, not live executable quotes. An observed value total is partial when coverage is below the number of supporters. Current value is not invested cost. One-sided markets and incomplete account scans cannot establish reliable net exposure.</div>"
    doc += f"<p>{len(TRADERS)} tracked traders · {len(partial)} incomplete scans · {len(rows)} outcome rows</p>"
    if partial:
        doc += "<p class='warning'>Incomplete accounts: " + esc(", ".join(sorted(partial))) + "</p>"
    doc += """<div class='notice'><label>Sport <select id='sport'><option value='ALL'>All</option><option>NBA</option><option>NFL</option><option>SOCCER</option></select></label> <label>View <select id='view'><option value='ALL'>All</option><option value='2'>Consensus</option><option value='1'>Singles</option></select></label> <label>Minimum shares <input id='minimum' type='number' value='0' min='0'></label></div>"""
    doc += body
    doc += """<script>
function filterCards(){
 const sport=document.getElementById('sport').value;
 const view=document.getElementById('view').value;
 const min=Number(document.getElementById('minimum').value)||0;
 document.querySelectorAll('article[data-sport]').forEach(card=>{
  const n=Number(card.dataset.count);
  card.style.display=(sport==='ALL'||sport===card.dataset.sport)&&
   (view==='ALL'||(view==='2'?n>=2:n===1))&&Number(card.dataset.shares)>=min?'':'none';
 });
}
['sport','view','minimum'].forEach(id=>document.getElementById(id).addEventListener('input',filterCards));
</script></body></html>"""
    Path(HTML_FILE).write_text(doc, encoding="utf-8")

def main():
    rows, partial, scanned = build()
    save_csv(rows)
    render(rows, partial, scanned)
    print(f"\nSaved {len(rows)} outcomes to {CSV_FILE} and {HTML_FILE}")
    for sport in ("NBA", "NFL", "SOCCER"):
        subset = [r for r in rows if r["sport"] == sport]
        print(f"{sport}: {sum(r['traders'] >= 2 for r in subset)} consensus, "
              f"{sum(r['traders'] == 1 for r in subset)} single-trader outcomes")
        for r in subset:
            if r["traders"] >= 2:
                print(f"  {r['traders']} traders | {r['market']} | {r['outcome']} | {r['quality']}")
    print("Partial scans:", ", ".join(sorted(partial)) if partial else "none")
    print("Open polymarket_report.html in your browser to view the dashboard.")

if __name__ == "__main__":
    main()
