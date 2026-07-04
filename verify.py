#!/usr/bin/env python3
"""
MoCHi Provably-Fair Verifier — Python reference implementation (no dependencies).

This reproduces, byte-for-byte, the randomness used to decide the RARITY of every
card pulled on https://getmochi.fun. It is the same math the MoCHi backend runs
(backend/main.py: provably_fair_roll + roll_to_rarity), re-implemented here so
anyone can independently confirm a pull was honest — without trusting MoCHi.

WHAT THIS PROVES
  - The committed server-seed fingerprint was not swapped (rigging check).
  - The roll hash + roll value + rarity were computed honestly from
    (server_seed, client_seed, nonce).

WHAT THIS DOES NOT PROVE (stated openly)
  - The specific CARD chosen within a rarity tier. That pick depends on live
    inventory and a house-edge weighting; it is not part of the provably-fair
    claim. The provably-fair claim covers: roll -> rarity.
  - The Fortune "soft pity" upgrade hash can only be re-checked if you also
    supply the pity-counter values for that pull (not included in pull data).

USAGE
  1) From a JSON pull record (recommended):
       python3 verify.py examples/sample-pull.json
  2) Inline arguments:
       python3 verify.py --server-seed <revealed> --client-seed <phrase> \
                          --nonce <n> --pack mugen_grail
  3) Interactive (it will prompt you):
       python3 verify.py

Pack rates are fetched live from https://getmochi.fun/public/packs by default
(--fetch-rates). On an offline / cross-origin host you can pass them manually
with --rates R,SR,SSR,SUR,EX (e.g. --rates 0.82,0.10,0.05,0.02,0.01).

License: MIT. See LICENSE.
"""
import argparse
import hashlib
import json
import sys
import urllib.request

RARITY_ORDER = ["R", "SR", "SSR", "SUR", "EX"]
PACKS_URL = "https://getmochi.fun/api/public/packs"


# ──────────────────────────────────────────────────────────────────────
# Core algorithm — exact reproduction of backend/main.py
# ──────────────────────────────────────────────────────────────────────
def provably_fair_roll(server_seed: str, client_seed: str, nonce: int):
    """SHA-256('server_seed:client_seed:nonce') -> (roll_value 0..9999, roll_hash)."""
    roll_hash = hashlib.sha256(f"{server_seed}:{client_seed}:{nonce}".encode()).hexdigest()
    roll_value = int(roll_hash, 16) % 10000
    return roll_value, roll_hash


def roll_to_rarity(roll_value: int, rates: dict) -> str:
    """Map 0..9999 -> rarity using cumulative rates (R,SR,SSR,SUR,EX order, truncate)."""
    cumulative = 0.0
    for rarity in RARITY_ORDER:
        cumulative += float(rates.get(rarity, 0))
        threshold = int(cumulative * 10000)  # truncate toward zero, NOT round
        if roll_value < threshold:
            return rarity
    return RARITY_ORDER[-1]


# ──────────────────────────────────────────────────────────────────────
# Rate loading
# ──────────────────────────────────────────────────────────────────────
def fetch_rates(pack: str) -> dict:
    """Live rates for `pack` from the public /api/public/packs endpoint."""
    req = urllib.request.Request(
        PACKS_URL,
        headers={"User-Agent": "MoCHi-Verifier/1.0 (+https://getmochi.fun)"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        packs = json.loads(r.read().decode())
    for p in packs:
        if p.get("id") == pack or p.get("href", "").rstrip("/").endswith(f"/{pack}"):
            return p["rates"]
    raise SystemExit(f"pack '{pack}' not found in {PACKS_URL}")


# ──────────────────────────────────────────────────────────────────────
# The actual verification
# ──────────────────────────────────────────────────────────────────────
def verify(server_seed, client_seed, nonce, rates,
           committed_hash=None, stored_roll_hash=None,
           stored_roll_value=None, stored_base_rarity=None):
    roll_value, roll_hash = provably_fair_roll(server_seed, client_seed, nonce)
    rarity = roll_to_rarity(roll_value, rates)

    checks = []
    ok = True

    # Rigging check — only if the user supplied the committed fingerprint.
    if committed_hash:
        calc = hashlib.sha256(server_seed.encode()).hexdigest()
        passed = (calc == committed_hash)
        checks.append(("Server-seed fingerprint (rigging check)",
                       passed, calc, committed_hash))
        ok &= passed

    # Honesty check — roll hash.
    if stored_roll_hash:
        passed = (roll_hash == stored_roll_hash)
        checks.append(("Roll hash (honesty check)", passed, roll_hash, stored_roll_hash))
        ok &= passed

    # Roll-value derivation.
    if stored_roll_value is not None:
        passed = (roll_value == int(stored_roll_value))
        checks.append(("Roll value (int(hash,16) % 10000)", passed, roll_value, stored_roll_value))
        ok &= passed

    # Rarity mapping.
    if stored_base_rarity:
        passed = (rarity == stored_base_rarity)
        checks.append(("Rarity (roll -> tier)", passed, rarity, stored_base_rarity))
        ok &= passed

    return ok, roll_value, roll_hash, rarity, checks


def report(ok, roll_value, rarity, checks):
    print(f"\n  Computed roll value : {roll_value} / 9999")
    print(f"  Computed rarity     : {rarity}\n")
    for name, passed, computed, expected in checks:
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name}")
        if not passed:
            print(f"          computed : {computed}")
            print(f"          expected : {expected}")
    print()
    print("  ===> ALL CHECKS PASSED — this pull's rarity was decided honestly."
          if ok and checks else
          "  ===> Verified against computed values (no stored receipt to compare).")
    if not ok:
        print("  ===> MISMATCH detected — see the FAIL lines above.")
    return ok


def main():
    ap = argparse.ArgumentParser(description="MoCHi provably-fair verifier")
    ap.add_argument("json_file", nargs="?", help="pull record JSON (see examples/)")
    ap.add_argument("--server-seed", help="revealed plaintext server seed")
    ap.add_argument("--client-seed", help="your client seed (lucky phrase)")
    ap.add_argument("--nonce", type=int, help="pull nonce (0,1,2,...)")
    ap.add_argument("--pack", help="pack id, e.g. mugen_grail")
    ap.add_argument("--rates", help="manual rates R,SR,SSR,SUR,EX (fractions)")
    ap.add_argument("--committed-hash", help="server_seed_hash shown BEFORE the pull")
    ap.add_argument("--roll-hash", help="stored roll_hash from your receipt")
    ap.add_argument("--roll-value", type=int, help="stored roll_value from your receipt")
    ap.add_argument("--base-rarity", help="stored base_rarity from your receipt")
    args = ap.parse_args()

    # Load from JSON if given, else CLI args, else interactive.
    if args.json_file:
        with open(args.json_file) as f:
            d = json.load(f)
        get = lambda k, d=None: d.get(k, d) if False else d.get(k)  # noqa
        server_seed = d["server_seed"]
        client_seed = d["client_seed"]
        nonce = d["nonce"]
        pack = d.get("pack")
        rates = d.get("rates")
        committed_hash = d.get("server_seed_hash")
        stored_roll_hash = d.get("roll_hash")
        stored_roll_value = d.get("roll_value")
        stored_base_rarity = d.get("base_rarity")
    else:
        server_seed = args.server_seed
        client_seed = args.client_seed
        nonce = args.nonce
        pack = args.pack
        committed_hash = args.committed_hash
        stored_roll_hash = args.roll_hash
        stored_roll_value = args.roll_value
        stored_base_rarity = args.base_rarity
        rates = None
        if args.server_seed is None:
            server_seed = input("Revealed server seed: ").strip()
            client_seed = input("Client seed (lucky phrase): ").strip()
            nonce = int(input("Nonce: ").strip())
            pack = input("Pack id (e.g. mugen_grail): ").strip() or None

    # Resolve rates: explicit > JSON > --rates > live fetch.
    if not rates:
        if args.rates:
            parts = [float(x) for x in args.rates.split(",")]
            rates = dict(zip(RARITY_ORDER, parts))
        elif pack:
            print(f"Fetching live rates for '{pack}' from {PACKS_URL} ...")
            rates = fetch_rates(pack)
        else:
            raise SystemExit("No rates: provide --rates, --pack, or a JSON file with rates.")

    ok, roll_value, roll_hash, rarity, checks = verify(
        server_seed, client_seed, nonce, rates,
        committed_hash=committed_hash,
        stored_roll_hash=stored_roll_hash,
        stored_roll_value=stored_roll_value,
        stored_base_rarity=stored_base_rarity,
    )
    report(ok, roll_value, rarity, checks)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
