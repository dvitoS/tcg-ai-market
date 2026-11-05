/** Smoke roundtrip for Radar ?share= codec shape (no vitest). */
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

const token = toBase64Url(
  JSON.stringify({ v: 1, q: "mew", min_edge: 4, set: "Celebrations" }),
);
const back = JSON.parse(fromBase64Url(token));
assert.equal(back.v, 1);
assert.equal(back.q, "mew");
assert.equal(back.min_edge, 4);
assert.equal(back.set, "Celebrations");
console.log("radar share roundtrip ok");
