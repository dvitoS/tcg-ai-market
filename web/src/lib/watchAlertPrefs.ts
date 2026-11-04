export const ALERT_DISMISS_KEY = "kestrel_watch_alert_dismissed";
export const ALERT_THRESHOLD_KEY = "kestrel_watch_alert_threshold";
export const ALERT_SURE_KEY = "kestrel_watch_alert_sure_only";
export const ALERT_PREFS_EVENT = "kestrel-watch-alert-prefs";

export function readDismissed(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(ALERT_DISMISS_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

export function writeDismissed(ids: string[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ALERT_DISMISS_KEY, JSON.stringify(ids));
  window.dispatchEvent(new Event(ALERT_PREFS_EVENT));
}

export function dismissAlert(cardId: string): string[] {
  const next = Array.from(new Set([...readDismissed(), String(cardId)]));
  writeDismissed(next);
  return next;
}

export function readThresholdPct(fallback = 5): number {
  if (typeof window === "undefined") return fallback;
  const thr = Number(window.localStorage.getItem(ALERT_THRESHOLD_KEY) || String(fallback));
  return Number.isFinite(thr) ? Math.min(50, Math.max(1, thr)) : fallback;
}

export function writeThresholdPct(value: number) {
  if (typeof window === "undefined") return;
  const clamped = Math.min(50, Math.max(1, value));
  window.localStorage.setItem(ALERT_THRESHOLD_KEY, String(clamped));
  window.dispatchEvent(new Event(ALERT_PREFS_EVENT));
}

export function readSureOnly(fallback = true): boolean {
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(ALERT_SURE_KEY);
  return raw == null ? fallback : raw !== "0";
}

export function writeSureOnly(value: boolean) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ALERT_SURE_KEY, value ? "1" : "0");
  window.dispatchEvent(new Event(ALERT_PREFS_EVENT));
}
