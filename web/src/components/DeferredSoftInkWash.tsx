"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const SoftInkWash = dynamic(
  () =>
    import("@/components/SoftInkWash").then((mod) => ({
      default: mod.SoftInkWash,
    })),
  { ssr: false },
);

/**
 * Soft Ink wash is atmosphere-only — mount after first paint / idle so it
 * never competes with Soft Nav LCP (brand text / hero card).
 */
export function DeferredSoftInkWash() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const arm = () => {
      if (!cancelled) setReady(true);
    };
    const w = window as Window & {
      requestIdleCallback?: (
        cb: () => void,
        opts?: { timeout: number },
      ) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (typeof w.requestIdleCallback === "function") {
      const id = w.requestIdleCallback(arm, { timeout: 900 });
      return () => {
        cancelled = true;
        w.cancelIdleCallback?.(id);
      };
    }
    const t = window.setTimeout(arm, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, []);

  if (!ready) return null;
  return <SoftInkWash />;
}
