/** Soft-launch funnel: landing → DOTD → Pro → Radar/Trade activation. */

import { apiUrl } from "@/lib/api";

export type FunnelEventName =
  | "landing_view"
  | "landing_cta_dotd"
  | "landing_cta_pro"
  | "dotd_view"
  | "dotd_cta"
  | "dotd_card_open"
  | "pro_view"
  | "pro_checkout_click"
  | "pro_open_radar"
  | "pro_open_trade"
  | "radar_activate"
  | "trade_activate"
  | "share_copy"
  | "share_png"
  | "spot_report";

const SESSION_KEY = "kestrel_funnel_session";
const ONCE_KEY = "kestrel_funnel_once";

function sessionId(): string {
  if (typeof window === "undefined") return "";
  try {
    const existing = window.sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `s_${Date.now().toString(36)}`;
    window.sessionStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    return `s_${Date.now().toString(36)}`;
  }
}

function onceKey(event: FunnelEventName, onceId?: string): string {
  return onceId ? `${event}:${onceId}` : event;
}

function alreadyFired(event: FunnelEventName, onceId?: string): boolean {
  if (typeof window === "undefined") return true;
  try {
    const raw = window.sessionStorage.getItem(ONCE_KEY);
    const set = new Set(raw ? (JSON.parse(raw) as string[]) : []);
    return set.has(onceKey(event, onceId));
  } catch {
    return false;
  }
}

function markFired(event: FunnelEventName, onceId?: string) {
  if (typeof window === "undefined") return;
  try {
    const raw = window.sessionStorage.getItem(ONCE_KEY);
    const list = raw ? (JSON.parse(raw) as string[]) : [];
    const next = Array.from(new Set([...list, onceKey(event, onceId)])).slice(
      -80,
    );
    window.sessionStorage.setItem(ONCE_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
}

export function trackFunnel(
  event: FunnelEventName,
  props?: Record<string, string | number | boolean | null | undefined>,
  opts?: { once?: boolean; onceId?: string },
) {
  if (typeof window === "undefined") return;
  if (opts?.once && alreadyFired(event, opts.onceId)) return;
  if (opts?.once) markFired(event, opts.onceId);

  const cleanProps: Record<string, string | number | boolean> = {};
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null) continue;
      cleanProps[key] = value;
    }
  }

  const body = JSON.stringify({
    events: [
      {
        event,
        session: sessionId(),
        props: Object.keys(cleanProps).length ? cleanProps : undefined,
      },
    ],
  });

  const url = apiUrl("/api/funnel/events");
  try {
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      const blob = new Blob([body], { type: "application/json" });
      if (navigator.sendBeacon(url, blob)) return;
    }
  } catch {
    /* fall through */
  }

  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {
    /* soft-launch: never block UX on telemetry */
  });
}
