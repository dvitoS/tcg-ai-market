"use client";

import { useRef, useState } from "react";

import { DotdShareCard } from "@/components/DotdShareCard";
import { useLocale } from "@/components/LocaleProvider";
import {
  buildDotdShareClipboardText,
  buildDotdShareUrl,
  dotdShareFilename,
  downloadDotdSharePng,
} from "@/lib/dotdExport";
import { trackFunnel } from "@/lib/funnel";
import { SITE_URL } from "@/lib/seo";
import type { RadarCard } from "@/lib/types";

export function DotdShareExport({
  card,
  spotLabel,
  fairLabel,
  edgeLabel,
  verdict,
}: {
  card: RadarCard;
  spotLabel: string;
  fairLabel: string;
  edgeLabel: string;
  verdict: string | null;
}) {
  const { t } = useLocale();
  const cardRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [linkBusy, setLinkBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Canonical origin on SSR + first client paint (avoid typeof window → #418).
  const shareUrl = buildDotdShareUrl(SITE_URL, card.id);

  function clipboardBody(url: string): string {
    return buildDotdShareClipboardText({
      blurb: t("dotd_share_blurb", { name: card.name }),
      verdict: verdict || t("glossary_under"),
      metrics: t("dotd_share_metrics", {
        spot: spotLabel,
        fair: fairLabel,
        edge: edgeLabel,
      }),
      note: t("dotd_export_note"),
      url,
    });
  }

  async function onExport() {
    if (!cardRef.current || busy) return;
    setBusy(true);
    setNote(null);
    setError(null);
    try {
      const { copied } = await downloadDotdSharePng(
        cardRef.current,
        dotdShareFilename(card.name),
      );
      trackFunnel("share_png", { surface: "dotd", clipboard: copied });
      setNote(
        copied ? t("dotd_export_done_clipboard") : t("dotd_export_done"),
      );
    } catch {
      setError(t("dotd_export_error"));
    } finally {
      setBusy(false);
    }
  }

  async function onCopyLink() {
    if (!shareUrl || linkBusy) return;
    setLinkBusy(true);
    setNote(null);
    setError(null);
    const text = clipboardBody(shareUrl);
    try {
      await navigator.clipboard.writeText(text);
      setNote(t("dotd_share_copied"));
      trackFunnel("share_copy", { surface: "dotd" });
    } catch {
      setNote(`${t("dotd_share_copied_fallback")}\n${shareUrl}`);
    } finally {
      setLinkBusy(false);
    }
  }

  return (
    <div className="dotd-share-export">
      <div className="detail-actions">
        <button
          type="button"
          className="btn-ghost"
          disabled={busy}
          onClick={() => void onExport()}
        >
          {busy ? t("dotd_export_busy") : t("dotd_export_image")}
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={linkBusy || !shareUrl}
          onClick={() => void onCopyLink()}
        >
          {linkBusy ? t("dotd_share_busy") : t("dotd_share_copy")}
        </button>
      </div>
      <p className="lot-meta">{t("dotd_share_hint")}</p>
      {note ? <p className="pro-open-note">{note}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
      <div className="trade-share-card-host" aria-hidden="true">
        <DotdShareCard
          ref={cardRef}
          card={card}
          spotLabel={spotLabel}
          fairLabel={fairLabel}
          edgeLabel={edgeLabel}
          verdict={verdict}
          shareUrl={shareUrl}
        />
      </div>
    </div>
  );
}
