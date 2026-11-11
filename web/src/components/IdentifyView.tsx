"use client";

import Image from "next/image";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { identifyFromOcrText, formatChange } from "@/lib/api";
import {
  enableContinuousFocus,
  focusAtPoint,
} from "@/lib/cameraFocus";
import {
  canvasFromFile,
  canvasFromVideo,
  recognizeCardText,
} from "@/lib/cardOcr";
import { onCardImageError, resolveCardImageUrl } from "@/lib/cardImage";
import { signalLabel } from "@/lib/i18n/messages";
import type { IdentifyMatch } from "@/lib/types";

type Phase = "idle" | "camera" | "ocr" | "match" | "done";

type FocusRing = { x: number; y: number; key: number };

async function openCameraStream(): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("no-media");
  }
  // Prefer rear camera + continuous AF when the UA understands focusMode.
  const withFocus = {
    audio: false,
    video: {
      facingMode: { ideal: "environment" as const },
      // Not in every TS lib yet — cast keeps runtime constraint.
      focusMode: { ideal: "continuous" },
    } as MediaTrackConstraints,
  };
  try {
    return await navigator.mediaDevices.getUserMedia(withFocus);
  } catch {
    try {
      return await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" } },
      });
    } catch {
      return await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: true,
      });
    }
  }
}

export function IdentifyView() {
  const { t, locale } = useLocale();
  const { formatSpot } = useCurrency();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [ocrText, setOcrText] = useState("");
  const [ocrPct, setOcrPct] = useState(0);
  const [matches, setMatches] = useState<IdentifyMatch[]>([]);
  const [hints, setHints] = useState<string[]>([]);
  const [number, setNumber] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [focusHint, setFocusHint] = useState(false);
  const [focusRing, setFocusRing] = useState<FocusRing | null>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
    setCameraReady(false);
    setFocusHint(false);
    setFocusRing(null);
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // Attach stream only after <video> mounts (phase === "camera").
  useEffect(() => {
    if (phase !== "camera") return;
    const video = videoRef.current;
    const stream = streamRef.current;
    if (!video || !stream) return;

    let cancelled = false;
    video.setAttribute("playsinline", "true");
    video.muted = true;
    video.srcObject = stream;

    const markReady = () => {
      if (cancelled || video.videoWidth <= 0) return;
      setCameraReady(true);
      setFocusHint(true);
      void enableContinuousFocus(stream);
    };
    video.addEventListener("loadedmetadata", markReady);
    video.addEventListener("playing", markReady);

    void video
      .play()
      .then(() => {
        if (!cancelled) markReady();
      })
      .catch(() => {
        if (!cancelled) {
          setError(t("identify_camera_error"));
          stopCamera();
          setPhase("idle");
        }
      });

    return () => {
      cancelled = true;
      video.removeEventListener("loadedmetadata", markReady);
      video.removeEventListener("playing", markReady);
    };
  }, [phase, stopCamera, t]);

  async function onTapFocus(event: ReactPointerEvent<HTMLDivElement>) {
    if (phase !== "camera" || !cameraReady || busy) return;
    const video = videoRef.current;
    const stream = streamRef.current;
    if (!video || !stream) return;
    // Ignore taps on the progress overlay / chrome.
    if ((event.target as HTMLElement).closest(".identify-progress")) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const xPct = ((event.clientX - rect.left) / rect.width) * 100;
    const yPct = ((event.clientY - rect.top) / rect.height) * 100;
    setFocusRing({ x: xPct, y: yPct, key: Date.now() });
    setFocusHint(true);
    await focusAtPoint(stream, video, event.clientX, event.clientY);
  }

  async function startCamera() {
    setError(null);
    stopCamera();
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    try {
      const stream = await openCameraStream();
      streamRef.current = stream;
      setCameraReady(false);
      setPhase("camera");
    } catch {
      setError(t("identify_camera_error"));
      setPhase("idle");
    }
  }

  async function runPipeline(canvas: HTMLCanvasElement) {
    setError(null);
    setMatches([]);
    setHints([]);
    setNumber(null);
    setPhase("ocr");
    setOcrPct(0);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.92),
    );
    setPreviewUrl(blob ? URL.createObjectURL(blob) : null);

    let text = "";
    try {
      text = await recognizeCardText(canvas, (p) => {
        setOcrPct(Math.round((p.progress || 0) * 100));
      });
    } catch {
      setError(t("identify_ocr_error"));
      setPhase("idle");
      return;
    }
    setOcrText(text);
    if (text.trim().length < 3) {
      setError(t("identify_ocr_empty"));
      setPhase("idle");
      return;
    }

    setPhase("match");
    try {
      const res = await identifyFromOcrText(text, 8);
      setMatches(res.matches || []);
      setHints(res.name_hints || []);
      setNumber(res.number || null);
      setPhase("done");
      if (!(res.matches || []).length) {
        setError(t("identify_no_match"));
      }
    } catch {
      setError(t("identify_match_error"));
      setPhase("idle");
    }
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video || !cameraReady) return;
    try {
      const canvas = canvasFromVideo(video);
      stopCamera();
      await runPipeline(canvas);
    } catch {
      setError(t("identify_ocr_error"));
      setPhase("idle");
    }
  }

  async function onFile(file: File | null) {
    if (!file) return;
    stopCamera();
    try {
      const canvas = await canvasFromFile(file);
      await runPipeline(canvas);
    } catch {
      setError(t("identify_ocr_error"));
      setPhase("idle");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function reset() {
    stopCamera();
    setPhase("idle");
    setError(null);
    setMatches([]);
    setOcrText("");
    setHints([]);
    setNumber(null);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  }

  const busy = phase === "ocr" || phase === "match";

  return (
    <div className="identify-page">
      <header className="identify-head">
        <p className="eyebrow">{t("identify_eyebrow")}</p>
        <h1>{t("identify_title")}</h1>
        <p className="identify-lede">{t("identify_lede")}</p>
      </header>

      <div className="identify-stage">
        <div
          className={`identify-viewport${phase === "camera" ? " is-live" : ""}`}
          onPointerUp={phase === "camera" ? (e) => void onTapFocus(e) : undefined}
        >
          {phase === "camera" ? (
            <video
              ref={videoRef}
              className="identify-video"
              playsInline
              muted
              autoPlay
              controls={false}
            />
          ) : previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="" className="identify-preview" />
          ) : (
            <div className="identify-placeholder">
              <p>{t("identify_placeholder")}</p>
            </div>
          )}
          {phase === "camera" && cameraReady && focusHint ? (
            <p className="identify-focus-hint">{t("identify_tap_focus")}</p>
          ) : null}
          {focusRing && phase === "camera" ? (
            <span
              key={focusRing.key}
              className="identify-focus-ring"
              style={{ left: `${focusRing.x}%`, top: `${focusRing.y}%` }}
              aria-hidden
            />
          ) : null}
          {busy ? (
            <div className="identify-progress" role="status">
              <strong>
                {phase === "ocr"
                  ? t("identify_ocr_progress", { pct: ocrPct })
                  : t("identify_matching")}
              </strong>
            </div>
          ) : null}
        </div>

        <div className="identify-actions">
          {phase === "camera" ? (
            <>
              <button
                type="button"
                className="btn-primary"
                onClick={() => void captureFrame()}
                disabled={!cameraReady || busy}
              >
                {cameraReady
                  ? t("identify_capture")
                  : t("identify_camera_warming")}
              </button>
              <button type="button" className="btn-ghost" onClick={reset}>
                {t("identify_cancel")}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="btn-primary"
                onClick={() => void startCamera()}
                disabled={busy}
              >
                {t("identify_open_camera")}
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => fileRef.current?.click()}
                disabled={busy}
              >
                {t("identify_upload")}
              </button>
              {phase === "done" ? (
                <button type="button" className="btn-ghost" onClick={reset}>
                  {t("identify_again")}
                </button>
              ) : null}
            </>
          )}
          {/* No capture= — that forces mobile camera/recording UI on Upload. */}
          <input
            ref={fileRef}
            type="file"
            accept="image/*,.jpg,.jpeg,.png,.webp,.heic,.heif"
            className="sr-only"
            onChange={(e) => void onFile(e.target.files?.[0] || null)}
          />
        </div>
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      {phase === "done" && (hints.length > 0 || number) ? (
        <p className="identify-clues">
          {number ? (
            <span>{t("identify_clue_number", { n: number })}</span>
          ) : null}
          {hints[0] ? (
            <span>{t("identify_clue_name", { name: hints[0] })}</span>
          ) : null}
        </p>
      ) : null}

      {matches.length > 0 ? (
        <section className="identify-results" aria-label={t("identify_results")}>
          <h2>{t("identify_results")}</h2>
          <p className="identify-lede">{t("identify_results_lede")}</p>
          <div className="identify-match-list">
            {matches.map((m) => {
              const card = m.card;
              return (
                <Link
                  key={card.id}
                  href={`/cards/${encodeURIComponent(card.id)}`}
                  className="identify-match"
                >
                  <div className="identify-match-art">
                    <Image
                      src={resolveCardImageUrl(card.id, card.image_url)}
                      alt=""
                      width={72}
                      height={100}
                      onError={(event) => onCardImageError(event, card.id)}
                    />
                  </div>
                  <div className="identify-match-body">
                    <strong>{card.name}</strong>
                    <span className="lot-meta">
                      {[card.set_name, card.rarity].filter(Boolean).join(" · ")}
                    </span>
                    {card.signal ? (
                      <span className="identify-verdict">
                        {signalLabel(locale, card.signal)}
                      </span>
                    ) : null}
                    <span className="identify-match-price">
                      {formatSpot(card.price)} ·{" "}
                      {formatChange(card.expected_change_pct)}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      ) : null}

      {ocrText && phase === "done" ? (
        <details className="identify-raw">
          <summary>{t("identify_raw_ocr")}</summary>
          <pre>{ocrText}</pre>
        </details>
      ) : null}
    </div>
  );
}
