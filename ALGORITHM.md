# MoCHi Provably-Fair Algorithm — Exact Specification

This is the precise, reproducible spec of how MoCHi decides the **rarity** of a gacha pull.
It is reverse-confirmed against the live backend (`backend/main.py`). Any correct verifier —
in any language — must reproduce these steps byte-for-byte.

There are **no secrets here**. Publishing the algorithm is the entire point of provably-fair:
security comes from the committed seed + one-way hashing, never from hiding the formula.

---

## 1. The three inputs

| Name | What it is | Known when? |
|---|---|---|
| `server_seed` | MoCHi's secret random string (64 hex chars = 32 bytes) | Hidden during use; revealed after the user rotates |
| `client_seed` | The user's "Lucky Phrase" | Public; set by the user (or auto-generated) |
| `nonce` | The pull counter (0, 1, 2, …) | Public; one per pull |

## 2. The roll

```
input_string = f"{server_seed}:{client_seed}:{nonce}"      # colon-separated, no spaces,
                                                            # nonce rendered as a decimal integer
roll_hash    = sha256(input_string).hexdigest()             # 64 lowercase hex chars
roll_value   = int(roll_hash, 16) % 10000                   # 0..9999
```

- Encoding is UTF-8.
- `int(roll_hash, 16)` parses the **entire** 64-char digest as one big integer (do not
  truncate it). In languages without big integers, use a BigInt (e.g. JS `BigInt("0x"+h)`).
- `% 10000` yields a value in `[0, 9999]`.

Python reference (`backend/main.py`):
```python
def provably_fair_roll(server_seed, client_seed, nonce):
    roll_hash = hashlib.sha256(f"{server_seed}:{client_seed}:{nonce}".encode()).hexdigest()
    roll_value = int(roll_hash, 16) % 10000
    return roll_value, roll_hash
```

## 3. Roll → rarity

Each pack has five rates — one per rarity — stored as **fractions** that sum to 1.0:

```
rates = {"R": rate_r, "SR": rate_sr, "SSR": rate_ssr, "SUR": rate_sur, "EX": rate_ex}
```

(e.g. `mugen_grail` ≈ `{"R":0.82, "SR":0.10, "SSR":0.05, "SUR":0.02, "EX":0.01}`.)

The rarity is chosen by **cumulative thresholds in fixed order R → SR → SSR → SUR → EX**:

```python
def roll_to_rarity(roll_value, rates):
    cumulative = 0.0
    for rarity in ["R", "SR", "SSR", "SUR", "EX"]:
        cumulative += rates[rarity]
        threshold = int(cumulative * 10000)     # TRUNCATE toward zero, do NOT round
        if roll_value < threshold:
            return rarity
    return "EX"   # safety net for float drift
```

**Critical details for re-implementers:**
- Iteration order is exactly **R, SR, SSR, SUR, EX**. A dict in Python 3.7+ preserves this; in
  other languages, hard-code the order.
- `threshold = int(cumulative * 10000)` is **truncation toward zero of an IEEE-754 double**,
  not rounding. Reproduce the same float arithmetic in the same order. Do **not** use
  `math.fsum` or `round()` — they can shift a boundary by 1.
- Rates must be the exact stored floats (these are exposed publicly at
  `GET https://getmochi.fun/public/packs` under each pack's `rates` field). Do not re-normalize.

### Worked example (`mugen_grail`, `roll_value = 9709`)
| rarity | cumulative | `int(cum*10000)` | range that wins it |
|---|---|---|---|
| R   | 0.82 | 8200  | 0 – 8199   |
| SR  | 0.92 | 9200  | 8200 – 9199 |
| SSR | 0.97 | 9700  | 9200 – 9699 |
| SUR | 0.99 | 9900  | 9700 – 9899 |
| EX  | 1.00 | 10000 | 9900 – 9999 |

`9709` is in the SUR range → **SUR**.

## 4. The rigging check (commitment verification)

Before the pull, the user is shown a fingerprint:
```
server_seed_hash = sha256(server_seed).hexdigest()
```
After rotation, the plaintext `server_seed` is revealed. The user re-computes
`sha256(revealed_server_seed)` and confirms it equals the `server_seed_hash` they were shown
**before** the pull. A match proves MoCHi did not swap the seed.

## 5. Fortune (pity) — partial / attested

Some packs (`has_pity = true`) apply a Fortune upgrade on top of the base rarity. Only the two
**soft** paths produce a verifiable hash:

```
fortune_hash (soft_sur) = sha256("fortune:{server_seed}:{client_seed}:{nonce}:sur:{pulls_since_sur}")
fortune_hash (soft_ssr) = sha256("fortune:{server_seed}:{client_seed}:{nonce}:ssr:{pulls_since_ssr}")
trigger_value           = int(fortune_hash, 16) % 10000
trigger fires when      trigger_value < trigger_rate * 10000      (trigger_rate default 0.30)
```

**Important:** `pulls_since_sur` / `pulls_since_ssr` (the pity counters at the moment of the
pull) are **not** included in the per-pull data MoCHi returns. So an external verifier cannot
recompute `fortune_hash` from pull data alone — it can only confirm a supplied `fortune_hash`
is well-formed, or accept the upgrade as server-attested. The two **hard**-pity paths are
deterministic and produce **no** hash. This is why the public claim is scoped to
**roll → base rarity**.

## 6. Out of scope of the provably-fair claim

- **The specific card chosen within a rarity tier.** After the rarity is fixed, MoCHi selects a
  card from the live in-stock inventory in that tier's price band, using a weighted pick. That
  pick is inventory-dependent and is **not** part of the hash. It is the designed house-edge
  layer and is not user-verifiable. `actual_rarity` may also differ from `final_rarity` when the
  rolled tier's band is empty ("inventory fallback") — this is attested, not hash-proven.

---

## Cross-implementation agreement

`verify.py`, `verify.js`, and `verifier.html` are independent implementations of sections 2–4.
For the worked example and for the roll values of nonces 0–5 with the demo seed, all three
produce identical output:

```
seed = "d3m0…0000", client = "i-love-mochi"
nonces 0..5 → roll values [3830, 2071, 7742, 4026, 9709, 7380]   (Python == Node == browser)
```
