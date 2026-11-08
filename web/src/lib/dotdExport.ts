import { exportSoftInkPng } from "@/lib/tradeExport";

export async function downloadDotdSharePng(
  node: HTMLElement,
  filename: string,
): Promise<{ copied: boolean }> {
  return exportSoftInkPng(node, filename);
}

export function dotdShareFilename(cardName: string): string {
  const slug = (cardName || "deal")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  const day = new Date().toISOString().slice(0, 10);
  return `kestrel-dotd-${day}-${slug || "deal"}.png`;
}

export function buildDotdShareUrl(origin: string, cardId: string): string {
  const base = origin.replace(/\/$/, "");
  return `${base}/cards/${encodeURIComponent(cardId)}`;
}

export function buildDotdShareClipboardText(args: {
  blurb: string;
  verdict: string;
  metrics: string;
  note: string;
  url: string;
}): string {
  return [args.blurb, args.verdict, args.metrics, args.note, args.url]
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n");
}
