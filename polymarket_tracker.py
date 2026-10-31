"""Find net consensus among tracked Polymarket positions for one event date.

Run: py polymarket_tracker.py
Requires: pip install requests
This reports position overlap, not betting advice.
"""
import csv
import re
import time
from collections import defaultdict
from datetime import date
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

TARGET_DATE = "2026-10-31"
MIN_TRADERS = 5
MIN_NET_SHARES = 1.0
PAGE_SIZE = 500
MAX_PAGES = 40
API = "https://data-api.polymarket.com/positions"
OUTPUT = "oct31_consensus.csv"

def numeric(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

def event_on_date(position):
    # Only include a market if its event slug explicitly identifies the date.
    slug = str(position.get("eventSlug") or position.get("slug") or "")
    return bool(re.search(r"(?<!\d)" + re.escape(TARGET_DATE) + r"(?!\d)", slug))

def fetch_positions(session, name, wallet):
    positions = []
    complete = False
    for page in range(MAX_PAGES):
        try:
            response = session.get(API, params={
                "user": wallet, "limit": PAGE_SIZE,
                "offset": page * PAGE_SIZE, "sizeThreshold": 0,
            }, timeout=35)
            response.raise_for_status()
            batch = response.json()
            if not isinstance(batch, list):
                raise ValueError("Expected a list of positions")
        except (requests.RequestException, ValueError) as exc:
            print(f"  INCOMPLETE: {exc}", flush=True)
            break
        positions.extend(batch)
        if len(batch) < PAGE_SIZE:
            complete = True
            break
        time.sleep(0.12)
    print(f"  {len(positions)} positions; complete={complete}", flush=True)
    return positions, complete

def main():
    try:
        date.fromisoformat(TARGET_DATE)
    except ValueError:
        raise SystemExit("Invalid TARGET_DATE")
    session = requests.Session()
    # conditionId -> trader -> outcome label -> shares
    exposure = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    meta = {}
    incomplete = []
    for name, wallet in TRADERS.items():
        print(f"Checking {name}...", flush=True)
        positions, complete = fetch_positions(session, name, wallet)
        if not complete:
            incomplete.append(name)
            # Do not count partial portfolios as full trader votes.
            continue
        for p in positions:
            if not event_on_date(p):
                continue
            condition = p.get("conditionId")
            outcome = p.get("outcome")
            size = numeric(p.get("size"))
            if not condition or outcome is None or size <= 0:
                continue
            outcome = str(outcome)
            exposure[condition][name][outcome] += size
            meta.setdefault(condition, {
                "title": str(p.get("title") or "Unknown market"),
                "slug": str(p.get("eventSlug") or p.get("slug") or ""),
            })

    results = []
    for condition, traders in exposure.items():
        supporters = defaultdict(list)
        for name, sides in traders.items():
            # Netting only makes sense for exactly two distinct outcomes
            # seen in this market across scanned traders.
            all_sides = {side for trader_sides in traders.values()
                         for side in trader_sides}
            if len(all_sides) != 2:
                continue
            side_a, side_b = sorted(all_sides)
            net = sides.get(side_a, 0) - sides.get(side_b, 0)
            if abs(net) < MIN_NET_SHARES:
                continue
            winner = side_a if net > 0 else side_b
            supporters[winner].append((name, abs(net)))
        for outcome, people in supporters.items():
            if len(people) < MIN_TRADERS:
                continue
            info = meta[condition]
            results.append({
                "market": info["title"],
                "outcome": outcome,
                "traders": len(people),
                "net_shares": round(sum(amount for _, amount in people), 2),
                "supporters": ", ".join(f"{name} ({amount:.2f})" for name, amount in sorted(people)),
                "url": "https://polymarket.com/event/" + info["slug"],
                "condition_id": condition,
            })
    results.sort(key=lambda r: (-r["traders"], -r["net_shares"]))
    with open(OUTPUT, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "market", "outcome", "traders", "net_shares",
            "supporters", "url", "condition_id"
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"\n=== {TARGET_DATE} CONSENSUS: {MIN_TRADERS}+ NET SUPPORTERS ===")
    if not results:
        print("No qualifying consensus found in fully scanned accounts.")
    for row in results:
        print(f"\n{row['traders']} traders | {row['market']} | {row['outcome']}")
        print(row["supporters"])
        print(row["url"])
    print(f"\nSaved {len(results)} results to {OUTPUT}")
    if incomplete:
        print("INCOMPLETE/EXCLUDED traders:", ", ".join(incomplete))
    print("NOTE: Net shares do not equal dollars, profit, or a reliable prediction.")
    print("NOTE: Date is inferred from event slug, not verified start time.")

if __name__ == "__main__":
    main()
