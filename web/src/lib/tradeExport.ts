import { toPng } from "html-to-image";

async function renderSoftInkPng(node: HTMLElement): Promise<string> {
  if (typeof window === "undefined") {
    throw new Error("Kestrel export needs a browser");
  }
  return toPng(node, {
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
}

function triggerPngDownload(dataUrl: string, filename: string): void {
  const anchor = document.createElement("a");
  anchor.href = dataUrl;
  anchor.download = filename;
  anchor.click();
}

/** Soft Ink offscreen card → PNG download (same-origin images only). */
export async function downloadSoftInkPng(
  node: HTMLElement,
  filename: string,
): Promise<void> {
  triggerPngDownload(await renderSoftInkPng(node), filename);
}

/** Best-effort clipboard image for Discord paste — falls back silently. */
export async function copySoftInkPngToClipboard(
  nodeOrDataUrl: HTMLElement | string,
): Promise<boolean> {
  if (typeof window === "undefined" || !navigator.clipboard?.write) {
    return false;
  }
  try {
    const dataUrl =
      typeof nodeOrDataUrl === "string"
        ? nodeOrDataUrl
        : await renderSoftInkPng(nodeOrDataUrl);
    const blob = await (await fetch(dataUrl)).blob();
    await navigator.clipboard.write([
      new ClipboardItem({ [blob.type || "image/png"]: blob }),
    ]);
    return true;
  } catch {
    return false;
  }
}

/** One render → download + best-effort clipboard. */
export async function exportSoftInkPng(
  node: HTMLElement,
  filename: string,
): Promise<{ copied: boolean }> {
  const dataUrl = await renderSoftInkPng(node);
  triggerPngDownload(dataUrl, filename);
  const copied = await copySoftInkPngToClipboard(dataUrl);
  return { copied };
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
