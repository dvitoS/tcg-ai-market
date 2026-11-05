"use client";

import { forwardRef } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { formatMoney } from "@/lib/api";

export type BinderShareSnapshot = {
  set_name: string;
  pct: number;
  owned: number;
  total: number;
  missing: number;
  missing_cost: number;
  missing_unpriced?: number;
};

export const BinderShareCard = forwardRef<
  HTMLDivElement,
  { snapshot: BinderShareSnapshot; shareUrl?: string | null }
>(function BinderShareCard({ snapshot, shareUrl }, ref) {
  const { t } = useLocale();
  const pct = Math.max(0, Math.min(100, snapshot.pct));
  return (
    <div ref={ref} className="binder-share-card" data-binder-report="1">
      <header className="trade-share-card-brand">
        <img
          src="/kestrel-logo.png"
          alt=""
          width={36}
          height={36}
          className="trade-share-card-mark"
        />
        <div>
          <p className="trade-share-card-kestrel">Kestrel</p>
          <p className="trade-share-card-tag">{t("binder_export_tag")}</p>
        </div>
      </header>

      <h2 className="binder-share-set">{snapshot.set_name}</h2>

      <div className="binder-share-pct">
        <strong>{pct.toFixed(1)}%</strong>
        <span>{t("binder_kpi_complete")}</span>
      </div>
      <div className="binder-progress binder-share-bar" aria-hidden>
        <span style={{ width: `${pct}%` }} />
      </div>

      <div className="binder-share-kpis">
        <div>
          <span>{t("binder_kpi_owned")}</span>
          <strong>
            {t("binder_owned_of", {
              owned: snapshot.owned,
              total: snapshot.total,
            })}
          </strong>
        </div>
        <div>
          <span>{t("binder_kpi_missing")}</span>
          <strong>{snapshot.missing}</strong>
        </div>
        <div>
          <span>{t("binder_kpi_cost")}</span>
          <strong>{formatMoney(snapshot.missing_cost)}</strong>
          {(snapshot.missing_unpriced ?? 0) > 0 ? (
            <em>
              {t("binder_unpriced", { n: snapshot.missing_unpriced ?? 0 })}
            </em>
          ) : null}
        </div>
      </div>

      <p className="binder-share-note">{t("binder_export_note")}</p>

      <footer className="trade-share-card-foot">
        <span>{t("binder_export_watermark")}</span>
        {shareUrl ? <span className="trade-share-card-url">{shareUrl}</span> : null}
      </footer>
    </div>
  );
});
