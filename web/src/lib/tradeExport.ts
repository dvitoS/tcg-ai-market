import { toPng } from "html-to-image";

function isInlineableSrc(src: string, origin: string): boolean {
  return (
    !src ||
    src.startsWith("data:") ||
    src.startsWith("blob:") ||
    src.startsWith(origin) ||
    src.startsWith("/")
  );
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("read failed"));
    reader.readAsDataURL(blob);
  });
}

function waitForImage(img: HTMLImageElement): Promise<void> {
  if (img.complete && img.naturalWidth > 0) return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      img.removeEventListener("load", done);
      img.removeEventListener("error", done);
      resolve();
    };
    img.addEventListener("load", done);
    img.addEventListener("error", done);
  });
}

/**
 * CDN card art is cross-origin. html-to-image skips tainted remote imgs unless
 * we embed them as data URLs first (pokemontcg / TCGdex / Scrydex all send ACAO *).
 */
async function inlineRemoteImages(root: HTMLElement): Promise<() => void> {
  const origin = window.location.origin;
  const imgs = Array.from(root.querySelectorAll("img"));
  const restores: Array<() => void> = [];

  await Promise.all(
    imgs.map(async (img) => {
      const src = img.currentSrc || img.getAttribute("src") || img.src || "";
      if (isInlineableSrc(src, origin)) return;
      try {
        const res = await fetch(src, { mode: "cors", credentials: "omit" });
        if (!res.ok) return;
        const dataUrl = await blobToDataUrl(await res.blob());
        if (!dataUrl.startsWith("data:")) return;
        const prev = img.getAttribute("src");
        img.setAttribute("src", dataUrl);
        restores.push(() => {
          if (prev != null) img.setAttribute("src", prev);
          else img.removeAttribute("src");
        });
        await waitForImage(img);
      } catch {
        /* leave remote — filter below will omit it rather than fail the PNG */
      }
    }),
  );

  return () => {
    for (const restore of restores) restore();
  };
}

function allowExportImage(el: Element, origin: string): boolean {
  if (!(el instanceof HTMLImageElement)) return true;
  const src = el.currentSrc || el.src || "";
  return isInlineableSrc(src, origin);
}

async function renderSoftInkPng(node: HTMLElement): Promise<string> {
  if (typeof window === "undefined") {
    throw new Error("Kestrel export needs a browser");
  }
  const origin = window.location.origin;
  const restore = await inlineRemoteImages(node);
  try {
    return await toPng(node, {
      cacheBust: true,
      pixelRatio: 2,
      backgroundColor: "#121212",
      // After inlining, only same-origin / data / relative remain.
      // Any fetch failure stays filtered out so export still succeeds.
      filter: (el) => allowExportImage(el, origin),
    });
  } finally {
    restore();
  }
}

function triggerPngDownload(dataUrl: string, filename: string): void {
  const anchor = document.createElement("a");
  anchor.href = dataUrl;
  anchor.download = filename;
  anchor.click();
}

/** Soft Ink offscreen card → PNG download (remote card art inlined). */
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

/** Discord / LGS paste pack: blurb + totals + disclaimer + live share URL. */
export function buildTradeShareClipboardText(args: {
  blurb: string;
  verdict: string;
  youSpot: string;
  themSpot: string;
  note: string;
  url: string;
}): string {
  return [
    args.blurb,
    args.verdict,
    `You ${args.youSpot} · Them ${args.themSpot}`,
    args.note,
    args.url,
  ]
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n");
}
