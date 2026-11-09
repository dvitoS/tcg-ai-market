/** Smoke roundtrip for Radar ?share= codec + OG title shape (no vitest). */
import assert from "node:assert/strict";

function toBase64Url(raw) {
  return Buffer.from(raw, "utf8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function fromBase64Url(token) {
  const b64 = token.replace(/-/g, "+").replace(/_/g, "/");
  const pad = b64.length % 4 === 0 ? "" : "=".repeat(4 - (b64.length % 4));
  return Buffer.from(b64 + pad, "base64").toString("utf8");
}

function formatChips(filters) {
  const parts = [];
  if (filters.q) parts.push(`“${filters.q}”`);
  if (filters.set) parts.push(filters.set);
  if (filters.rarity) parts.push(filters.rarity);
  if (filters.min_edge != null && filters.min_edge > 0) {
    const e = filters.min_edge;
    parts.push(`edge ≥ ${e >= 10 ? Math.round(e) : e}%`);
  }
  return parts;
}

function seoTitle(filters) {
  const chips = formatChips(filters);
  if (chips.length === 1) return `${chips[0]} — Kestrel Radar`;
  if (chips.length > 1) {
    return `Radar lens · ${chips.slice(0, 2).join(" · ")} — Kestrel`;
  }
  return "Kestrel Radar — sure underpriced Pokémon cards";
}

const token = toBase64Url(
  JSON.stringify({ v: 1, q: "mew", min_edge: 4, set: "Celebrations" }),
);
const back = JSON.parse(fromBase64Url(token));
assert.equal(back.v, 1);
assert.equal(back.q, "mew");
assert.equal(back.min_edge, 4);
assert.equal(back.set, "Celebrations");
assert.equal(
  seoTitle({ q: "mew", min_edge: 4, set: "Celebrations" }),
  "Radar lens · “mew” · Celebrations — Kestrel",
);
assert.equal(seoTitle({ q: "mew" }), "“mew” — Kestrel Radar");
assert.match(
  `/radar/share-image?share=${encodeURIComponent(token)}`,
  /^\/radar\/share-image\?share=/,
);
console.log("radar share roundtrip + OG title ok");
