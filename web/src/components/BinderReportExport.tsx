"use client";

import { useRef, useState } from "react";

import {
  BinderShareCard,
  type BinderShareSnapshot,
} from "@/components/BinderShareCard";
import { useLocale } from "@/components/LocaleProvider";
import {
  binderReportFilename,
  buildBinderShareUrl,
  downloadBinderReportPng,
} from "@/lib/binderExport";

export function BinderReportExport({
  snapshot,
}: {
  snapshot: BinderShareSnapshot;
}) {
  const { t } = useLocale();
  const cardRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [linkBusy, setLinkBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const shareUrl =
    typeof window !== "undefined"
      ? buildBinderShareUrl(window.location.origin, snapshot.set_name)
      : null;

  async function onExport() {
    if (!cardRef.current || busy) return;
    setBusy(true);
    setNote(null);
    setError(null);
    try {
      await downloadBinderReportPng(
        cardRef.current,
        binderReportFilename(snapshot.set_name),
      );
      setNote(t("binder_export_done"));
    } catch {
      setError(t("binder_export_error"));
    } finally {
      setBusy(false);
    }
  }

  async function onCopyLink() {
    if (!shareUrl || linkBusy) return;
    setLinkBusy(true);
    setNote(null);
    setError(null);
    try {
      await navigator.clipboard.writeText(
        `${t("binder_share_blurb", { set: snapshot.set_name, pct: snapshot.pct.toFixed(0) })}\n${shareUrl}`,
      );
      setNote(t("binder_share_copied"));
    } catch {
      setError(t("binder_share_error"));
    } finally {
      setLinkBusy(false);
    }
  }

  return (
    <div className="binder-report-export">
      <div className="detail-actions binder-export-actions">
        <button
          type="button"
          className="btn-ghost"
          disabled={busy}
          onClick={() => void onExport()}
        >
          {busy ? t("binder_export_busy") : t("binder_export_image")}
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={linkBusy || !shareUrl}
          onClick={() => void onCopyLink()}
        >
          {linkBusy ? t("binder_share_busy") : t("binder_share_copy")}
        </button>
      </div>
      {note ? <p className="pro-open-note">{note}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
      <div className="trade-share-card-host" aria-hidden="true">
        <BinderShareCard
          ref={cardRef}
          snapshot={snapshot}
          shareUrl={shareUrl}
        />
      </div>
    </div>
  );
}
