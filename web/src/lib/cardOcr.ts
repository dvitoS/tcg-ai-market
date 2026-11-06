/** Client-side card OCR via tesseract.js (lazy-loaded). */

export type OcrProgress = {
  status: string;
  progress: number;
};

export async function recognizeCardText(
  image: HTMLCanvasElement | HTMLImageElement | File | Blob | string,
  onProgress?: (p: OcrProgress) => void,
): Promise<string> {
  const { createWorker } = await import("tesseract.js");
  const worker = await createWorker("eng", 1, {
    logger: (m) => {
      if (!onProgress) return;
      const progress = typeof m.progress === "number" ? m.progress : 0;
      onProgress({
        status: String(m.status || "recognizing"),
        progress,
      });
    },
  });
  try {
    const result = await worker.recognize(image);
    return String(result.data.text || "").trim();
  } finally {
    await worker.terminate();
  }
}

/** Downscale large camera frames so OCR stays snappy on phones. */
export function canvasFromVideo(
  video: HTMLVideoElement,
  maxEdge = 1280,
): HTMLCanvasElement {
  const vw = video.videoWidth || 640;
  const vh = video.videoHeight || 480;
  const scale = Math.min(1, maxEdge / Math.max(vw, vh));
  const w = Math.max(1, Math.round(vw * scale));
  const h = Math.max(1, Math.round(vh * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.drawImage(video, 0, 0, w, h);
  return canvas;
}

export async function canvasFromFile(
  file: File,
  maxEdge = 1280,
): Promise<HTMLCanvasElement> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error("Could not read image"));
      el.src = url;
    });
    const scale = Math.min(1, maxEdge / Math.max(img.width, img.height));
    const w = Math.max(1, Math.round(img.width * scale));
    const h = Math.max(1, Math.round(img.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas unavailable");
    ctx.drawImage(img, 0, 0, w, h);
    return canvas;
  } finally {
    URL.revokeObjectURL(url);
  }
}
