/**
 * eBay Marketplace Account Deletion webhook (Cloudflare Worker).
 *
 * Challenge hash = SHA256(challengeCode + verificationToken + endpointUrl)
 * endpointUrl must match the URL registered in eBay Notifications exactly.
 * For the challenge we prefer the request URL (no query) so it always matches
 * what eBay just called.
 */

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      // Avoid CF caching challenge responses.
      "cache-control": "no-store",
    },
  });
}

function endpointFromRequest(url) {
  // Exact path eBay hit, no query string, no trailing slash.
  const path = url.pathname.replace(/\/$/, "") || "/";
  return `${url.origin}${path}`;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/$/, "") || "/";

    if (path === "/health" && request.method === "GET") {
      return json({
        status: "ok",
        endpoint_configured: env.EBAY_DELETION_ENDPOINT ? "yes" : "no",
        token_configured: env.EBAY_VERIFICATION_TOKEN ? "yes" : "no",
        resolved_endpoint: endpointFromRequest(url).replace(/\/health$/, ""),
      });
    }

    if (path === "/" && request.method === "GET") {
      return json({
        service: "tcg-ai-market-ebay-webhook",
        deletion_path: "/ebay/account-deletion",
      });
    }

    if (path !== "/ebay/account-deletion") {
      return json({ error: "not found" }, 404);
    }

    const token = (env.EBAY_VERIFICATION_TOKEN || "").trim();
    const configured = (env.EBAY_DELETION_ENDPOINT || "").trim().replace(/\/$/, "");
    const calledAs = endpointFromRequest(url);

    if (request.method === "GET") {
      const challengeCode =
        url.searchParams.get("challenge_code") ||
        url.searchParams.get("challengeCode");
      if (!challengeCode) {
        return json({ error: "missing challenge_code" }, 400);
      }
      if (!token) {
        return json({ error: "EBAY_VERIFICATION_TOKEN not set" }, 500);
      }

      // Prefer configured URL if present; fall back to the URL eBay actually hit.
      const endpointForHash = configured || calledAs;
      const challengeResponse = await sha256Hex(
        `${challengeCode}${token}${endpointForHash}`,
      );
      return json({ challengeResponse });
    }

    if (request.method === "POST") {
      try {
        await request.json();
      } catch {
        // empty / non-JSON body is fine
      }
      return new Response(null, {
        status: 200,
        headers: { "cache-control": "no-store" },
      });
    }

    return json({ error: "method not allowed" }, 405);
  },
};
