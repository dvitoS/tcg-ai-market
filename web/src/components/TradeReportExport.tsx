"use client";

import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

import { useLocale } from "@/components/LocaleProvider";
import { TradeShareCard } from "@/components/TradeShareCard";
import { trackFunnel } from "@/lib/funnel";
import { exportSoftInkPng, tradeReportFilename } from "@/lib/tradeExport";
import type { TradeResponse } from "@/lib/types";

export function TradeReportExport({
  trade,
  shareUrl,
  onEnsureShare,
}: {
  trade: TradeResponse;
  shareUrl?: string | null;
  /** Create / refresh a public share link before embedding it on the PNG. */
  onEnsureShare?: () => Promise<string | null>;
}) {
  const { t } = useLocale();
  const cardRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeUrl, setActiveUrl] = useState<string | null>(shareUrl || null);

  useEffect(() => {
    if (shareUrl) setActiveUrl(shareUrl);
  }, [shareUrl]);

  async function exportPng(withLink: boolean) {
    if (!cardRef.current || busy) return;
    setBusy(true);
    setNote(null);
    setError(null);
    try {
      let url = activeUrl || shareUrl || null;
      if (withLink && onEnsureShare) {
        url = (await onEnsureShare()) || url;
      }
      flushSync(() => {
        setActiveUrl(url);
      });
      const node = cardRef.current;
      if (!node) throw new Error("missing card");
      const { copied } = await exportSoftInkPng(
        node,
        tradeReportFilename(trade.verdict),
      );
      trackFunnel("share_png", {
        surface: "trade",
        with_link: withLink,
        clipboard: copied,
      });
      setNote(
        copied ? t("trade_export_done_clipboard") : t("trade_export_done"),
      );
    } catch {
      setError(t("trade_export_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="trade-report-export">
      <div className="trade-report-export-actions">
        <button
          type="button"
          className="btn-primary"
          disabled={busy}
          onClick={() => void exportPng(false)}
        >
          {busy ? t("trade_export_busy") : t("trade_export_image")}
        </button>
        {onEnsureShare ? (
          <button
            type="button"
            className="btn-ghost"
            disabled={busy}
            onClick={() => void exportPng(true)}
          >
            {t("trade_export_with_link")}
          </button>
        ) : null}
      </div>
      <p className="lot-meta">{t("trade_export_hint")}</p>
      {note ? <p className="pro-open-note">{note}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
      <div className="trade-share-card-host" aria-hidden="true">
        <TradeShareCard
          ref={cardRef}
          trade={trade}
          shareUrl={activeUrl || shareUrl}
        />
      </div>
    </div>
  );
}
