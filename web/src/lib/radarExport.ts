import { exportSoftInkPng } from "@/lib/tradeExport";

export async function downloadRadarSharePng(
  node: HTMLElement,
  filename: string,
): Promise<{ copied: boolean }> {
  return exportSoftInkPng(node, filename);
}

export function radarShareFilename(): string {
  const day = new Date().toISOString().slice(0, 10);
  return `kestrel-radar-${day}.png`;
}
