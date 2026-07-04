#!/usr/bin/env node
/*
 * MoCHi Provably-Fair Verifier — Node.js reference implementation (no dependencies).
 *
 * Byte-for-byte reproduction of the MoCHi backend randomness
 * (backend/main.py: provably_fair_roll + roll_to_rarity), so anyone can
 * independently confirm a pull's RARITY was decided honestly.
 *
 * Same scope/honest limitations as verify.py — see that file or ALGORITHM.md.
 *
 * Usage:
 *   node verify.js examples/sample-pull.json
 *   node verify.js --server-seed <revealed> --client-seed <phrase> \
 *                  --nonce 4 --rates 0.82,0.10,0.05,0.02,0.01
 *
 * License: MIT.
 */
"use strict";
const crypto = require("crypto");
const fs = require("fs");

const RARITY_ORDER = ["R", "SR", "SSR", "SUR", "EX"];

function provablyFairRoll(serverSeed, clientSeed, nonce) {
  // Note: nonce must render as a plain decimal integer, matching Python f-string.
  const rollHash = crypto.createHash("sha256")
    .update(`${serverSeed}:${clientSeed}:${nonce}`, "utf8")
    .digest("hex");
  // int(hash,16) % 10000  — BigInt keeps this exact for the 64-hex digest.
  const rollValue = Number(BigInt("0x" + rollHash) % 10000n);
  return { rollValue, rollHash };
}

function rollToRarity(rollValue, rates) {
  let cumulative = 0.0;
  for (const rarity of RARITY_ORDER) {
    cumulative += Number(rates[rarity] || 0);
    const threshold = Math.trunc(cumulative * 10000); // truncate, NOT round
    if (rollValue < threshold) return rarity;
  }
  return RARITY_ORDER[RARITY_ORDER.length - 1];
}

function verify({ serverSeed, clientSeed, nonce, rates,
                  serverSeedHash, rollHash: storedHash,
                  rollValue: storedValue, baseRarity }) {
  const { rollValue, rollHash } = provablyFairRoll(serverSeed, clientSeed, nonce);
  const rarity = rollToRarity(rollValue, rates);
  const checks = [];
  let ok = true;

  if (serverSeedHash) {
    const calc = crypto.createHash("sha256").update(serverSeed, "utf8").digest("hex");
    const passed = calc === serverSeedHash;
    checks.push(["Server-seed fingerprint (rigging check)", passed, calc, serverSeedHash]);
    ok &&= passed;
  }
  if (storedHash) {
    const passed = rollHash === storedHash;
    checks.push(["Roll hash (honesty check)", passed, rollHash, storedHash]);
    ok &&= passed;
  }
  if (storedValue !== undefined && storedValue !== null) {
    const passed = rollValue === Number(storedValue);
    checks.push(["Roll value (int(hash,16) % 10000)", passed, rollValue, storedValue]);
    ok &&= passed;
  }
  if (baseRarity) {
    const passed = rarity === baseRarity;
    checks.push(["Rarity (roll -> tier)", passed, rarity, baseRarity]);
    ok &&= passed;
  }
  return { ok, rollValue, rollHash, rarity, checks };
}

function report({ ok, rollValue, rarity, checks }) {
  console.log(`\n  Computed roll value : ${rollValue} / 9999`);
  console.log(`  Computed rarity     : ${rarity}\n`);
  for (const [name, passed, computed, expected] of checks) {
    console.log(`  [${passed ? "PASS" : "FAIL"}] ${name}`);
    if (!passed) {
      console.log(`          computed : ${computed}`);
      console.log(`          expected : ${expected}`);
    }
  }
  console.log(ok && checks.length
    ? "\n  ===> ALL CHECKS PASSED — this pull's rarity was decided honestly."
    : "\n  ===> Verified against computed values (no stored receipt to compare).");
  if (!ok) console.log("  ===> MISMATCH detected — see the FAIL lines above.");
  return ok;
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--server-seed") out.serverSeed = argv[++i];
    else if (a === "--client-seed") out.clientSeed = argv[++i];
    else if (a === "--nonce") out.nonce = Number(argv[++i]);
    else if (a === "--rates") {
      const parts = argv[++i].split(",").map(Number);
      out.rates = Object.fromEntries(parts.map((v, i) => [RARITY_ORDER[i], v]));
    } else if (a === "--committed-hash") out.serverSeedHash = argv[++i];
    else if (a === "--roll-hash") out.rollHash = argv[++i];
    else if (a === "--roll-value") out.rollValue = Number(argv[++i]);
    else if (a === "--base-rarity") out.baseRarity = argv[++i];
    else if (!a.startsWith("--")) out.jsonFile = a;
  }
  return out;
}

// Accept either snake_case (as written by verify.py / sample-pull.json) or camelCase.
function normalize(d) {
  const g = (k1, k2) => (d[k1] !== undefined ? d[k1] : d[k2]);
  return {
    serverSeed: g("server_seed", "serverSeed"),
    clientSeed: g("client_seed", "clientSeed"),
    nonce: g("nonce"),
    rates: g("rates"),
    serverSeedHash: g("server_seed_hash", "serverSeedHash"),
    rollHash: g("roll_hash", "rollHash"),
    rollValue: g("roll_value", "rollValue"),
    baseRarity: g("base_rarity", "baseRarity"),
  };
}

function main() {
  const a = parseArgs(process.argv.slice(2));
  let data;
  if (a.jsonFile) {
    data = normalize(JSON.parse(fs.readFileSync(a.jsonFile, "utf8")));
  } else {
    data = {
      serverSeed: a.serverSeed, clientSeed: a.clientSeed, nonce: a.nonce,
      rates: a.rates, serverSeedHash: a.serverSeedHash, rollHash: a.rollHash,
      rollValue: a.rollValue, baseRarity: a.baseRarity,
    };
  }
  if (!data.serverSeed || !data.clientSeed || data.nonce === undefined || !data.rates) {
    console.error("Missing inputs. Pass a JSON file or --server-seed/--client-seed/--nonce/--rates.");
    process.exit(2);
  }
  const result = verify(data);
  report(result);
  process.exit(result.ok ? 0 : 1);
}

main();
