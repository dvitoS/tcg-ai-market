import { toPng } from "html-to-image";

/** Soft Ink offscreen card → PNG (same-origin images only). */
export async function downloadSoftInkPng(
  node: HTMLElement,
  filename: string,
): Promise<void> {
  if (typeof window === "undefined") {
    throw new Error("Kestrel export needs a browser");
  }
  const dataUrl = await toPng(node, {
    cacheBust: true,
    pixelRatio: 2,
    backgroundColor: "#121212",
    // Same-origin logo only — skip remote card art CORS failures.
    filter: (el) => {
      if (!(el instanceof HTMLImageElement)) return true;
      const src = el.currentSrc || el.src || "";
      return (
        src.startsWith(window.location.origin) ||
        src.startsWith("data:") ||
        src.startsWith("blob:") ||
        src.startsWith("/")
      );
    },
  });
  const anchor = document.createElement("a");
  anchor.href = dataUrl;
  anchor.download = filename;
  anchor.click();
}

export async function downloadTradeReportPng(
  node: HTMLElement,
  filename: string,
): Promise<void> {
  return downloadSoftInkPng(node, filename);
}

export function tradeReportFilename(verdict: string): string {
  const slug = (verdict || "fair").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `kestrel-trade-${slug || "fair"}.png`;
}
