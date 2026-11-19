"use client";

import { useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchSpotReportStatus, reportWrongSpot } from "@/lib/api";
import { trackFunnel } from "@/lib/funnel";
import type { SpotReportPublic } from "@/lib/types";

const storageKey = (cardId: string) => `kestrel_spot_report:${cardId}`;

type LocalReport = {
  reportId: string;
  status: SpotReportPublic["status"];
  spotAtReport: number | null;
};

function readLocal(cardId: string): LocalReport | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(storageKey(cardId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as LocalReport;
    if (!parsed?.reportId || !parsed?.status) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeLocal(cardId: string, value: LocalReport) {
  try {
    window.localStorage.setItem(storageKey(cardId), JSON.stringify(value));
  } catch {
    /* ignore quota */
  }
}

export function WrongSpotReport({
  cardId,
  spot,
  initialReport,
}: {
  cardId: string;
  spot?: number | null;
  initialReport?: SpotReportPublic | null;
}) {
  const { t } = useLocale();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<SpotReportPublic | null>(
    () => initialReport ?? null,
  );

  useEffect(() => {
    setReport(initialReport ?? null);
  }, [cardId, initialReport]);

  useEffect(() => {
    const local = readLocal(cardId);
    if (!local) return;
    if (initialReport?.status === "resolved") {
      writeLocal(cardId, {
        reportId: initialReport.id,
        status: "resolved",
        spotAtReport: initialReport.spot ?? local.spotAtReport,
      });
      return;
    }
    if (local.status === "open" || local.status === "acked") {
      let alive = true;
      void fetchSpotReportStatus(cardId)
        .then((body) => {
          if (!alive || !body.report) return;
          setReport(body.report);
          writeLocal(cardId, {
            reportId: body.report.id,
            status: body.report.status,
            spotAtReport: body.report.spot ?? local.spotAtReport,
          });
        })
        .catch(() => {
          /* keep local */
        });
      return () => {
        alive = false;
      };
    }
  }, [cardId, initialReport]);

  const status = report?.status ?? null;
  const done =
    status === "open" || status === "acked" || status === "resolved";

  async function onReport() {
    if (busy || done) return;
    setBusy(true);
    setError(null);
    try {
      const row = await reportWrongSpot({
        card_id: cardId,
        spot: spot ?? null,
        note: "wrong_spot",
      });
      trackFunnel("spot_report", { card_id: cardId });
      const next: SpotReportPublic = {
        id: row.id,
        status: (row.status as SpotReportPublic["status"]) || "open",
        spot: spot ?? null,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
      };
      setReport(next);
      writeLocal(cardId, {
        reportId: next.id,
        status: next.status,
        spotAtReport: spot ?? null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("detail_report_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrong-spot-report">
      {status === "resolved" ? (
        <p className="lot-meta" title={t("detail_spot_fixed_hint")}>
          {t("detail_spot_fixed")}
        </p>
      ) : status === "open" || status === "acked" ? (
        <p className="lot-meta">{t("detail_report_checking")}</p>
      ) : (
        <button
          type="button"
          className="btn-ghost"
          disabled={busy}
          onClick={() => void onReport()}
        >
          {busy ? t("detail_report_busy") : t("detail_report_wrong_spot")}
        </button>
      )}
      {error ? <p className="form-error">{error}</p> : null}
    </div>
  );
}
