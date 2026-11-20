import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/** Public Soft Ink → Supabase Auth (OAuth only). Anon key is safe in the browser. */
export function getSupabaseBrowser(): SupabaseClient | null {
  const url = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim();
  const anon = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "").trim();
  if (!url || !anon) return null;
  return createClient(url, anon, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
      detectSessionInUrl: true,
      flowType: "pkce",
    },
  });
}

export function isGoogleAuthConfigured(): boolean {
  return Boolean(
    (process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim() &&
      (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "").trim(),
  );
}
