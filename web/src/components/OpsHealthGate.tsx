"use client";

import { useAuth } from "@/components/AuthProvider";
import { DataHealthPanel } from "@/components/DataHealthPanel";

/** Ops-only panel — hide from cold marketing visitors. */
export function OpsHealthGate() {
  const { user, loading } = useAuth();
  if (loading || !user) return null;
  return <DataHealthPanel />;
}
