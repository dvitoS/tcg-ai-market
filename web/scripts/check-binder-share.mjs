/** Smoke for Binder ?set= share URL + OG title shape (no vitest). */
import assert from "node:assert/strict";

function cleanBinderShareSet(raw) {
  if (!raw || typeof raw !== "string") return null;
  const text = raw.trim().slice(0, 120);
  return text || null;
}

function binderShareSeoTitle(setName) {
  if (setName) return `${setName} — Kestrel binder`;
  return "Kestrel binder — set completion";
}

function buildBinderShareUrl(origin, setName) {
  const base = origin.replace(/\/$/, "");
  const params = new URLSearchParams();
  const cleaned = cleanBinderShareSet(setName);
  if (cleaned) params.set("set", cleaned);
  return `${base}/binder?${params.toString()}`;
}

assert.equal(cleanBinderShareSet("  Base Set  "), "Base Set");
assert.equal(cleanBinderShareSet("   "), null);
assert.equal(
  binderShareSeoTitle("Celebrations"),
  "Celebrations — Kestrel binder",
);
assert.equal(
  binderShareSeoTitle(null),
  "Kestrel binder — set completion",
);
assert.equal(
  buildBinderShareUrl("https://www.kestreltcg.app", "Celebrations"),
  "https://www.kestreltcg.app/binder?set=Celebrations",
);
assert.match(
  `/binder/share-image?set=${encodeURIComponent("Celebrations")}`,
  /^\/binder\/share-image\?set=/,
);
console.log("binder share + OG title ok");
