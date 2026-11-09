"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { identifyFromOcrText, formatChange } from "@/lib/api";
import {
  canvasFromFile,
  canvasFromVideo,
  recognizeCardText,
} from "@/lib/cardOcr";
import { onCardImageError, resolveCardImageUrl } from "@/lib/cardImage";
import { signalLabel } from "@/lib/i18n/messages";
import type { IdentifyMatch } from "@/lib/types";

type Phase = "idle" | "camera" | "ocr" | "match" | "done";

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

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
    setCameraReady(false);
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  async function startCamera() {
    setError(null);
    stopCamera();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play();
      }
      setPhase("camera");
      setCameraReady(true);
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
    if (previewUrl) URL.revokeObjectURL(previewUrl);
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
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
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
        <div className="identify-viewport">
          {phase === "camera" ? (
            <video
              ref={videoRef}
              className="identify-video"
              playsInline
              muted
              autoPlay
            />
          ) : previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="" className="identify-preview" />
          ) : (
            <div className="identify-placeholder">
              <p>{t("identify_placeholder")}</p>
            </div>
          )}
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
                {t("identify_capture")}
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
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="sr-only"
            onChange={(e) => void onFile(e.target.files?.[0] || null)}
          />
        </div>
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      {phase === "done" && (hints.length > 0 || number) ? (
        <p className="identify-clues">
          {number ? (
            <span>
              {t("identify_clue_number", { n: number })}
            </span>
          ) : null}
          {hints[0] ? (
            <span>
              {t("identify_clue_name", { name: hints[0] })}
            </span>
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
