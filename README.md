# MoCHi Provably-Fair Verifier

Independently verify that a **MoCHi** ([getmochi.fun](https://getmochi.fun)) gacha pull was
decided honestly — using nothing but standard SHA-256. No trust required.

This repository is the open-source companion to MoCHi's built-in
[`/gacha/verify`](https://getmochi.fun/gacha/verify) page. The math is identical; the
difference is that **this code is public, dependency-free, and runnable anywhere**, so a
skeptic doesn't have to take MoCHi's word for it.

> 🔐 **Why this exists.** "Provably fair" only means something if you can check it yourself.
> MoCHi commits to a secret (its hash) *before* you pull, then reveals the secret *after*.
> Because SHA-256 is one-way, the committed hash locks MoCHi in — it can't swap the secret
> without the hash changing. You re-do the math with the revealed secret and confirm the
> result matches. That's the whole trick. See [`ALGORITHM.md`](ALGORITHM.md) for the exact spec.

---

## The 30-second version

1. Pull a pack on MoCHi.
2. On MoCHi's verify page → **Seeds** tab → **Rotate Server Seed** (this reveals the old secret).
3. Open the **History** tab → copy the pull's `revealed server seed`, your `client seed`, the `nonce`, and the receipt values.
4. Verify it:

```bash
# Python
python3 verify.py examples/sample-pull.json

# Node
node verify.js examples/sample-pull.json

# Or open the page in any browser:
verifier.html
```

All three will report `✅ ALL CHECKS PASSED` for the worked example.

---

## What's in this repo

| File | What it is |
|---|---|
| `verifier.html` | A single self-contained web page (inline JS, Web Crypto). Drop it anywhere — open with a double-click, host on any static site. |
| `verify.py` | Python reference verifier. Standard library only — no `pip install`. |
| `verify.js` | Node.js reference verifier. No dependencies. |
| `ALGORITHM.md` | The exact algorithm spec (for anyone re-implementing in another language). |
| `examples/sample-pull.json` | A synthetic worked example with known-good values (NOT a real pull — safe to publish). |
| `LICENSE` | MIT. |

The three implementations (`verifier.html`, `verify.py`, `verify.js`) are intentionally
redundant. They must always agree. If you ever find an input where they disagree, that's a bug
— please open an issue.

---

## How to use each verifier

### `verify.py`
```bash
# From a JSON pull record:
python3 verify.py examples/sample-pull.json

# Inline (rates fetched live from getmochi.fun):
python3 verify.py --server-seed <revealed> --client-seed <phrase> --nonce 4 --pack mugen_grail

# Fully offline (paste rates too):
python3 verify.py --server-seed <revealed> --client-seed <phrase> --nonce 4 \
                  --rates 0.82,0.10,0.05,0.02,0.01

# Interactive (it will prompt you):
python3 verify.py
```

### `verify.js`
```bash
node verify.js examples/sample-pull.json
node verify.js --server-seed <revealed> --client-seed <phrase> --nonce 4 --rates 0.82,0.10,0.05,0.02,0.01
```

### `verifier.html`
Just open it in a browser. On `getmochi.fun` it auto-loads live pack rates; anywhere else
(local file, GitHub Pages, your own host) you can type the rates manually. Everything runs
locally — no network calls except the optional rate fetch.

---

## What this proves (and what it honestly can't)

### ✅ It proves
- The **rarity tier** of your pull (R / SR / SSR / SUR / EX) was computed honestly from
  `SHA-256("server_seed:client_seed:nonce")`.
- MoCHi did **not** swap its committed server seed (the fingerprint matches).

### 🟡 It can't prove (stated openly)
- **Which specific card** you received *within* that tier. That pick depends on live inventory
  and a weighting step; it is not part of the hash. This is the same limitation every gacha
  has. MoCHi's provably-fair claim is scoped to **roll → rarity**.
- The **Fortune "soft pity"** upgrade. Its hash mixes in pity-counter values that aren't
  included in pull data, so it is server-attested rather than independently reproducible.
  (Hard-pity upgrades are deterministic and contain no hash.)

**In short: provably-fair *rarity*, honestly scoped — never "provably-fair *everything*."**

---

## The commit-then-reveal flow (why it can't be rigged)

```
 BEFORE pull:  MoCHi locks server_seed, shows you  SHA-256(server_seed)   ← the fingerprint
 YOU PULL:     result = SHA-256(server_seed : client_seed : nonce)
 AFTER rotate: MoCHi reveals plaintext server_seed
 YOU VERIFY:   SHA-256(revealed_seed) == fingerprint?        ← rigging check
               SHA-256(seed:client:nonce) == stored roll?    ← honesty check
```

The only way to rig a pull would be to use a *different* server seed than the one committed —
but that would change the fingerprint, which you recorded before the pull. SHA-256 is one-way,
so the fingerprint reveals nothing about the seed (you can't predict rolls from it). That's
why transparency doesn't create an exploit: you can verify the past, but you cannot predict the
future.

---

## Integrity (prove this page wasn't secretly swapped)

A live verifier on the operator's own site can be quietly changed at any time. To remove
that doubt, the footer of `verifier.html` carries a **version** (`v1.0.0`), and each release
publishes the **SHA-256** of the exact file. You can recompute it yourself and compare:

```bash
# Fetch the live page and hash it — must match the value below for v1.0.0
curl -s https://getmochi.fun/fairness | sha256sum
```

**v1.0.0 — `verifier.html` SHA-256:**
```
e62fdd8b0c13171ffe3564cdf1b3263a28f9e0aa1d464f598e755461c9315398
```

If the live page ever differs from this hash, either MoCHi shipped a new version (check the
footer version + this file for a new entry) or the page was tampered with. The pinned copy on
[GitHub Pages](https://miner1qaz-ops.github.io/provably-fair-verifier/verifier.html) is
served straight from this tagged release and is the reference an independent party should use.

---

## License

MIT — see [`LICENSE`](LICENSE). Use it, fork it, host it, audit it.
