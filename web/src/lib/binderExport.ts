import { downloadSoftInkPng } from "@/lib/tradeExport";

export async function downloadBinderReportPng(
  node: HTMLElement,
  filename: string,
): Promise<void> {
  return downloadSoftInkPng(node, filename);
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
