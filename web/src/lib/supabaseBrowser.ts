import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let browserClient: SupabaseClient | null | undefined;

/**
 * Public Soft Ink → Supabase Auth (OAuth only). Anon/publishable key is safe in the browser.
 *
 * PKCE stores a code verifier before redirecting to Google. That verifier must survive the
 * round-trip in durable browser storage. Soft Ink copies the access token into its own API
 * auth via setAccessToken after /auth/callback — we do NOT auto-detect the URL here because
 * AuthCallbackView exchanges the code explicitly (detectSessionInUrl would race and clear
 * the verifier first).
 */
export function getSupabaseBrowser(): SupabaseClient | null {
  if (typeof window === "undefined") return null;
  if (browserClient !== undefined) return browserClient;

  const url = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim();
  const anon = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "").trim();
  if (!url || !anon) {
    browserClient = null;
    return null;
  }

  browserClient = createClient(url, anon, {
    auth: {
      persistSession: true,
      autoRefreshToken: false,
      detectSessionInUrl: false,
      flowType: "pkce",
      storage: window.localStorage,
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
