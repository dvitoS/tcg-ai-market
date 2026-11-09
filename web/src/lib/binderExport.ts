import { exportSoftInkPng } from "@/lib/tradeExport";

export async function downloadBinderReportPng(
  node: HTMLElement,
  filename: string,
): Promise<{ copied: boolean }> {
  return exportSoftInkPng(node, filename);
}

export function binderReportFilename(setName: string): string {
  const slug = (setName || "set")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return `kestrel-binder-${slug || "set"}.png`;
}

export function cleanBinderShareSet(raw: string | null | undefined): string | null {
  if (!raw || typeof raw !== "string") return null;
  const text = raw.trim().slice(0, 120);
  return text || null;
}

export function buildBinderShareUrl(origin: string, setName: string): string {
  const base = origin.replace(/\/$/, "");
  const params = new URLSearchParams();
  const cleaned = cleanBinderShareSet(setName);
  if (cleaned) params.set("set", cleaned);
  return `${base}/binder?${params.toString()}`;
}

/** Discord / Reddit unfurl title for a shared binder set. */
export function binderShareSeoTitle(setName: string | null): string {
  if (setName) return `${setName} — Kestrel binder`;
  return "Kestrel binder — set completion";
}

/** Discord / Reddit unfurl description for a shared binder set. */
export function binderShareSeoDescription(setName: string | null): string {
  const lead = setName
    ? `${setName} set completion on Kestrel.`
    : "Set completion checklist on Kestrel.";
  return `${lead} Owned / missing / buy-cost — no private P&L. Sign in to open the live binder.`;
}

/** Plain-language Discord paste — % / owned / missing / buy-cost, never P&L. */
export function buildBinderShareClipboardText(args: {
  blurb: string;
  ownedLine: string;
  missingLine: string;
  costLine: string;
  note: string;
  url: string;
}): string {
  return [
    args.blurb.trim(),
    args.ownedLine.trim(),
    args.missingLine.trim(),
    args.costLine.trim(),
    args.note.trim(),
    args.url,
  ]
    .filter(Boolean)
    .join("\n");
}
