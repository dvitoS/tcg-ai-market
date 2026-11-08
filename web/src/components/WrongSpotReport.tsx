"use client";

import { useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { reportWrongSpot } from "@/lib/api";
import { trackFunnel } from "@/lib/funnel";

export function WrongSpotReport({
  cardId,
  spot,
}: {
  cardId: string;
  spot?: number | null;
}) {
  const { t } = useLocale();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onReport() {
    if (busy || done) return;
    setBusy(true);
    setError(null);
    try {
      await reportWrongSpot({
        card_id: cardId,
        spot: spot ?? null,
        note: "wrong_spot",
      });
      trackFunnel("spot_report", { card_id: cardId });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("detail_report_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrong-spot-report">
      {done ? (
        <p className="lot-meta">{t("detail_report_thanks")}</p>
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
