
import requests
from collections import defaultdict

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

URL = "https://data-api.polymarket.com/positions"
session = requests.Session()

overlaps = defaultdict(dict)
failed = []

for name, wallet in TRADERS.items():
    print(f"Checking {name}...", flush=True)

    positions = []
    offset = 0

    try:
        while True:
            response = session.get(
                URL,
                params={
                    "user": wallet,
                    "limit": 500,
                    "offset": offset,
                    "sizeThreshold": 0
                },
                timeout=30
            )

            if response.status_code != 200:
                print("  API error:", response.status_code)
                print(" ", response.text[:300])
                failed.append(name)
                break

            batch = response.json()

            if not isinstance(batch, list):
                print("  Unexpected response:", str(batch)[:300])
                failed.append(name)
                break

            positions.extend(batch)

            if len(batch) < 500:
                break

            offset += 500

            if offset >= 5000:
                print("  Reached 5000-position scan limit")
                failed.append(name)
                break

        print(f"  Retrieved {len(positions)} positions")

        for position in positions:
            condition = position.get("conditionId")
            outcome = position.get("outcome")
            title = position.get("title", "Unknown market")

            if not condition or outcome is None:
                continue

            try:
                size = float(position.get("size") or 0)
            except (ValueError, TypeError):
                continue

            if size <= 0:
                continue

            key = (condition, str(outcome))

            overlaps[key][name] = {
                "title": title,
                "outcome": outcome,
                "size": size,
                "slug": position.get("slug", "")
            }

    except requests.RequestException as error:
        print("  Connection error:", error)
        failed.append(name)

print("\n=== SHARED POSITIONS: 5+ TRADERS ===")

matches = [
    (key, holders)
    for key, holders in overlaps.items()
    if len(holders) >= 5
]

matches.sort(key=lambda item: len(item[1]), reverse=True)

if not matches:
    print("No positions held by 5 or more scanned traders.")
else:
    for key, holders in matches:
        example = next(iter(holders.values()))

        print("\nMARKET:", example["title"])
        print("OUTCOME:", example["outcome"])
        print("TRADERS:", len(holders))

        for name, info in holders.items():
            print(f"  {name}: {info['size']:.2f} shares")

        if example["slug"]:
            print(
                "LINK:",
                "https://polymarket.com/event/" + example["slug"]
            )

print("\n=== TOP 15 OVERLAPS (ANY DATE) ===")

ranked = sorted(
    overlaps.items(),
    key=lambda item: len(item[1]),
    reverse=True
)

for key, holders in ranked[:15]:
    example = next(iter(holders.values()))
    print(
        f"{len(holders)} traders | "
        f"{example['title']} | "
        f"{example['outcome']}"
    )

print("\nFAILED OR INCOMPLETE ACCOUNTS:", failed)
print("DONE")
