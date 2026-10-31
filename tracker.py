
import requests
import time

TRADERS = [
    "BreakTheBank", "joseph00677", "UpTheBlues",
    "googleplaya", "HomeRunHazard", "Flaznorp",
    "theowalcott", "gmpm2", "Diabolical-Prize",
    "monkeymashingkeyboard", "takeormake",
    "SmartPredictOrNot", "juice-fruit", "Jsram",
    "RN1", "ArielFilipino", "nigiri99",
    "justwins", "keeptheblueflagflyinghigh",
    "BillyGating"
]

URL = "https://data-api.polymarket.com/v1/leaderboard"

# Wallets already confirmed from your earlier results
found = {
    "RN1": "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
    "BreakTheBank": "0xf0318c32136c2db7fec88b84869aee6a1106c80c",
    "joseph00677": "0xcdcccd0f2d86e450d973da415ad2430e5cc7935a",
    "HomeRunHazard": "0x5268527977f700f9bf9b6d5cd843859e4e70135d",
    "Jsram": "0x83720820a8aa6c3f20ad71850e7a1a17d16c5223"
}

target_names = {name.lower(): name for name in TRADERS}

session = requests.Session()

# Test configurations instead of assuming which one works
configs = [
    {"category": "SPORT", "timePeriod": "ALL"},
    {"category": "SPORTS", "timePeriod": "ALL"},
    {"category": "OVERALL", "timePeriod": "ALL"},
]

working_config = None

print("=== TESTING LEADERBOARD API ===")

for config in configs:
    params = {
        **config,
        "orderBy": "PNL",
        "limit": 50,
        "offset": 0
    }

    try:
        response = session.get(URL, params=params, timeout=20)

        print(
            config,
            "| Status:",
            response.status_code
        )

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, list):
                working_config = config
                print("WORKING CONFIGURATION:", config)
                break

        else:
            print("API DETAILS:", response.text[:500])

    except requests.RequestException as error:
        print("Connection error:", error)

if working_config is None:
    print("\nNo working leaderboard configuration found.")

else:
    print("\n=== SEARCHING FOR YOUR 20 TRADERS ===")

    for offset in range(0, 5000, 50):
        params = {
            **working_config,
            "orderBy": "PNL",
            "limit": 50,
            "offset": offset
        }

        try:
            response = session.get(
                URL,
                params=params,
                timeout=20
            )

            if response.status_code != 200:
                print("Stopped at offset:", offset)
                print("Status:", response.status_code)
                print("Details:", response.text[:500])
                break

            batch = response.json()

            if not isinstance(batch, list) or not batch:
                print("No more leaderboard results.")
                break

            for trader in batch:
                username = trader.get("userName", "")
                target = target_names.get(username.lower())

                if target:
                    wallet = trader.get("proxyWallet")

                    if wallet:
                        found[target] = wallet

            print(
                f"Scanned {offset + len(batch)} traders "
                f"| Found {len(found)}/20"
            )

            if len(found) == len(TRADERS):
                break

            if len(batch) < 50:
                break

            time.sleep(0.2)

        except requests.RequestException as error:
            print("Request failed:", error)
            break

print("\n=== MATCHED WALLETS ===")

for name in TRADERS:
    wallet = found.get(name)

    if wallet:
        print(name, "|", wallet)
    else:
        print(name, "| NOT FOUND")

print(f"\nTOTAL FOUND: {len(found)}/20")
print("DONE")
