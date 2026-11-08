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

export function buildBinderShareUrl(origin: string, setName: string): string {
  const base = origin.replace(/\/$/, "");
  const params = new URLSearchParams();
  params.set("set", setName);
  return `${base}/binder?${params.toString()}`;
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
