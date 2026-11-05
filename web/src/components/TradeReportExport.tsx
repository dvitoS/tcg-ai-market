"use client";

import { useRef, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { TradeShareCard } from "@/components/TradeShareCard";
import {
  downloadTradeReportPng,
  tradeReportFilename,
} from "@/lib/tradeExport";
import type { TradeResponse } from "@/lib/types";

export function TradeReportExport({
  trade,
  shareUrl,
}: {
  trade: TradeResponse;
  shareUrl?: string | null;
}) {
  const { t } = useLocale();
  const cardRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onExport() {
    if (!cardRef.current || busy) return;
    setBusy(true);
    setNote(null);
    setError(null);
    try {
      await downloadTradeReportPng(
        cardRef.current,
        tradeReportFilename(trade.verdict),
      );
      setNote(t("trade_export_done"));
    } catch {
      setError(t("trade_export_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="trade-report-export">
      <button
        type="button"
        className="btn-ghost"
        disabled={busy}
        onClick={() => void onExport()}
      >
        {busy ? t("trade_export_busy") : t("trade_export_image")}
      </button>
      {note ? <p className="pro-open-note">{note}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
      <div className="trade-share-card-host" aria-hidden="true">
        <TradeShareCard ref={cardRef} trade={trade} shareUrl={shareUrl} />
      </div>
    </div>
  );
}
