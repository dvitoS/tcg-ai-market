"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  fetchMe,
  getAccessToken,
  loginRequest,
  setAccessToken,
  signupRequest,
} from "@/lib/api";
import {
  getSupabaseBrowser,
  isGoogleAuthConfigured,
} from "@/lib/supabaseBrowser";
import type { AuthUser } from "@/lib/types";

type SignupOutcome = {
  needsConfirmation: boolean;
  message?: string | null;
};

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<SignupOutcome>;
  /** Start Google OAuth (Supabase). redirectTo lands on Soft Ink /auth/callback. */
  loginWithGoogle: (redirectTo: string) => Promise<void>;
  googleAuthEnabled: boolean;
  refresh: () => Promise<void>;
  logout: () => void;
  /** Local/demo only. Returns false in production when demo login is rejected. */
  ensureDemoSession: () => Promise<boolean>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = getAccessToken();
    try {
      const me = await fetchMe(token);
      if (me.authenticated && me.user) {
        setUser(me.user);
        if (!token && me.user.dev) {
          setAccessToken("dev-local-token");
        }
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const session = await loginRequest(email, password);
    setAccessToken(session.access_token);
    setUser(session.user);
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const result = await signupRequest(email, password);
    if (result.access_token && result.user && !result.needs_confirmation) {
      setAccessToken(result.access_token);
      setUser(result.user);
    }
    return {
      needsConfirmation: Boolean(result.needs_confirmation),
      message: result.message,
    };
  }, []);

  const loginWithGoogle = useCallback(async (redirectTo: string) => {
    const client = getSupabaseBrowser();
    if (!client) {
      throw new Error("Google sign-in is not configured.");
    }
    const { data, error } = await client.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo,
        queryParams: {
          prompt: "select_account",
        },
      },
    });
    if (error) throw error;
    // Browser navigates to data.url; keep a throw path if the SDK returns no URL.
    if (data?.url && typeof window !== "undefined") {
      window.location.assign(data.url);
    }
  }, []);

  const logout = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  const ensureDemoSession = useCallback(async () => {
    if (getAccessToken()) {
      await refresh();
      return true;
    }
    try {
      await login("dev@local", "demo");
      return true;
    } catch {
      // Production (AUTH_DISABLED=0) rejects demo credentials — don't spam the console.
      return false;
    }
  }, [login, refresh]);

  const googleAuthEnabled = isGoogleAuthConfigured();

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      signup,
      loginWithGoogle,
      googleAuthEnabled,
      refresh,
      logout,
      ensureDemoSession,
    }),
    [
      user,
      loading,
      login,
      signup,
      loginWithGoogle,
      googleAuthEnabled,
      refresh,
      logout,
      ensureDemoSession,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
