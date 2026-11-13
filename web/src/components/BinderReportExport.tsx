"use client";

import { useRef, useState } from "react";

import {
  BinderShareCard,
  type BinderShareSnapshot,
} from "@/components/BinderShareCard";
import { useLocale } from "@/components/LocaleProvider";
import { formatMoney } from "@/lib/api";
import {
  binderReportFilename,
  buildBinderShareClipboardText,
  buildBinderShareUrl,
  downloadBinderReportPng,
} from "@/lib/binderExport";
import { trackFunnel } from "@/lib/funnel";
import { SITE_URL } from "@/lib/seo";

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

  // Canonical origin on SSR + first client paint (avoid typeof window → #418).
  const shareUrl = buildBinderShareUrl(SITE_URL, snapshot.set_name);

  function clipboardBody(url: string): string {
    const pct = Math.max(0, Math.min(100, snapshot.pct)).toFixed(0);
    return buildBinderShareClipboardText({
      blurb: t("binder_share_blurb", {
        set: snapshot.set_name,
        pct,
      }),
      ownedLine: t("binder_share_owned", {
        owned: snapshot.owned,
        total: snapshot.total,
      }),
      missingLine: t("binder_share_missing", { n: snapshot.missing }),
      costLine: t("binder_share_cost", {
        value: formatMoney(snapshot.missing_cost),
      }),
      note: t("binder_export_note"),
      url,
    });
  }

  async function onExport() {
    if (!cardRef.current || busy) return;
    setBusy(true);
    setNote(null);
    setError(null);
    try {
      const { copied } = await downloadBinderReportPng(
        cardRef.current,
        binderReportFilename(snapshot.set_name),
      );
      trackFunnel("share_png", { surface: "binder", clipboard: copied });
      setNote(
        copied ? t("binder_export_done_clipboard") : t("binder_export_done"),
      );
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
    const text = clipboardBody(shareUrl);
    try {
      await navigator.clipboard.writeText(text);
      setNote(t("binder_share_copied"));
      trackFunnel("share_copy", { surface: "binder" });
    } catch {
      setNote(`${t("binder_share_copied_fallback")}\n${shareUrl}`);
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
      <p className="lot-meta">{t("binder_share_hint")}</p>
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
