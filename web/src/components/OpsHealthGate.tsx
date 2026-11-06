"use client";

import { useAuth } from "@/components/AuthProvider";
import { DataHealthPanel } from "@/components/DataHealthPanel";

/** Ops-only panel — Soft Ink operator allowlist (not every signed-in user). */
export function OpsHealthGate() {
  const { user, loading } = useAuth();
  if (loading || !user?.ops) return null;
  return <DataHealthPanel />;
}
