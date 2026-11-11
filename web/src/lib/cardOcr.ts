/** Client-side card OCR via tesseract.js (lazy-loaded). */

export type OcrProgress = {
  status: string;
  progress: number;
};

const TESSERACT_VERSION = "5.1.1";
const TESSERACT_CDN = `https://cdn.jsdelivr.net/npm/tesseract.js@${TESSERACT_VERSION}/dist`;
const TESSERACT_CORE_CDN = `https://cdn.jsdelivr.net/npm/tesseract.js-core@${TESSERACT_VERSION}`;
const TESSDATA_CDN = "https://tessdata.projectnaptha.com/4.0.0";

/** Soft contrast stretch so foil glare / phone photos OCR more reliably. */
export function preprocessForOcr(source: HTMLCanvasElement): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = source.width;
  canvas.height = source.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.drawImage(source, 0, 0);
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const { data } = image;
  let min = 255;
  let max = 0;
  for (let i = 0; i < data.length; i += 4) {
    const y = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    if (y < min) min = y;
    if (y > max) max = y;
  }
  const span = Math.max(1, max - min);
  for (let i = 0; i < data.length; i += 4) {
    const y = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    const stretched = Math.max(0, Math.min(255, ((y - min) / span) * 255));
    // Mild threshold toward ink — helps card titles on busy art.
    const v = stretched < 140 ? stretched * 0.75 : Math.min(255, stretched * 1.08);
    data[i] = v;
    data[i + 1] = v;
    data[i + 2] = v;
  }
  ctx.putImageData(image, 0, 0);
  return canvas;
}

export async function recognizeCardText(
  image: HTMLCanvasElement | HTMLImageElement | File | Blob | string,
  onProgress?: (p: OcrProgress) => void,
): Promise<string> {
  const { createWorker, PSM } = await import("tesseract.js");
  // Pin worker/core to CDN — Next.js bundling often breaks the default worker URL.
  const worker = await createWorker("eng", 1, {
    workerPath: `${TESSERACT_CDN}/worker.min.js`,
    corePath: `${TESSERACT_CORE_CDN}/tesseract-core-simd-lstm.wasm.js`,
    langPath: TESSDATA_CDN,
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
    await worker.setParameters({
      // Uniform block — card title + HP + number cluster.
      tessedit_pageseg_mode: PSM.SINGLE_BLOCK,
      preserve_interword_spaces: "1",
    });
    const input =
      image instanceof HTMLCanvasElement ? preprocessForOcr(image) : image;
    const result = await worker.recognize(input);
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
  const vw = video.videoWidth || 0;
  const vh = video.videoHeight || 0;
  if (vw < 2 || vh < 2) {
    throw new Error("Camera frame not ready");
  }
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
  // Prefer createImageBitmap so EXIF orientation from phone photos is applied.
  let bitmap: ImageBitmap | null = null;
  try {
    bitmap = await createImageBitmap(file, {
      imageOrientation: "from-image",
    } as ImageBitmapOptions);
  } catch {
    bitmap = null;
  }

  if (bitmap) {
    try {
      const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
      const w = Math.max(1, Math.round(bitmap.width * scale));
      const h = Math.max(1, Math.round(bitmap.height * scale));
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas unavailable");
      ctx.drawImage(bitmap, 0, 0, w, h);
      return canvas;
    } finally {
      bitmap.close();
    }
  }

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
