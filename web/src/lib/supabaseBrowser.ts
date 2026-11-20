import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let browserClient: SupabaseClient | null | undefined;

/**
 * Public Soft Ink → Supabase Auth (OAuth only). Anon/publishable key is safe in the browser.
 *
 * PKCE stores a code verifier before redirecting to Google. That verifier must survive the
 * round-trip, so we use sessionStorage (persistSession true). Soft Ink still copies the
 * access token into its own API auth via setAccessToken after /auth/callback.
 */
export function getSupabaseBrowser(): SupabaseClient | null {
  if (browserClient !== undefined) return browserClient;

  const url = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim();
  const anon = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "").trim();
  if (!url || !anon || typeof window === "undefined") {
    browserClient = null;
    return null;
  }

  browserClient = createClient(url, anon, {
    auth: {
      persistSession: true,
      autoRefreshToken: false,
      detectSessionInUrl: true,
      flowType: "pkce",
      storage: window.sessionStorage,
    },
  });
  return browserClient;
}

export function isGoogleAuthConfigured(): boolean {
  return Boolean(
    (process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim() &&
      (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "").trim(),
  );
}
