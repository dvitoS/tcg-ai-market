"use client";

import { forwardRef } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { formatChange, formatMoney } from "@/lib/api";
import type { TradeResponse, TradeSide } from "@/lib/types";

function verdictClass(verdict: string): string {
  if (verdict === "YOU_AHEAD") return "trade-you";
  if (verdict === "THEM_AHEAD") return "trade-them";
  return "trade-fair";
}

function verdictLabelKey(
  verdict: string,
): "trade_v_you_ahead" | "trade_v_them_ahead" | "trade_v_fair" {
  if (verdict === "YOU_AHEAD") return "trade_v_you_ahead";
  if (verdict === "THEM_AHEAD") return "trade_v_them_ahead";
  return "trade_v_fair";
}

function CardSide({ title, side }: { title: string; side: TradeSide }) {
  const { t } = useLocale();
  const lines = side.lines.slice(0, 8);
  const extra = Math.max(0, side.lines.length - lines.length);
  return (
    <div className="trade-report-side">
      <div className="trade-report-side-head">
        <h3>{title}</h3>
        <p>
          {formatMoney(side.spot_total)} spot · {formatMoney(side.fair_total)}{" "}
          {t("glossary_fair")}
        </p>
      </div>
      <ul className="trade-report-lines">
        {lines.length === 0 ? (
          <li className="trade-report-empty">{t("trade_share_empty_side")}</li>
        ) : (
          lines.map((line) => (
            <li
              key={`${line.card_id}-${line.condition || "NM"}-${line.printing || "Normal"}-${line.quantity}`}
            >
              <span className="trade-report-name">
                {line.name || line.card_id}
              </span>
              <span className="trade-report-meta">
                ×{line.quantity}
                {line.spot != null ? ` · ${formatMoney(line.spot)}` : ""}
              </span>
            </li>
          ))
        )}
        {extra > 0 ? (
          <li className="trade-report-more">
            {t("trade_export_more", { n: extra })}
          </li>
        ) : null}
      </ul>
    </div>
  );
}

export const TradeShareCard = forwardRef<
  HTMLDivElement,
  { trade: TradeResponse; shareUrl?: string | null }
>(function TradeShareCard({ trade, shareUrl }, ref) {
  const { t } = useLocale();
  return (
    <div ref={ref} className="trade-share-card" data-trade-report="1">
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
          <p className="trade-share-card-tag">{t("trade_export_tag")}</p>
        </div>
      </header>

      <div className="trade-share-card-board">
        <CardSide title={t("trade_you_give")} side={trade.you} />
        <CardSide title={t("trade_them_give")} side={trade.them} />
      </div>

      <div className={`trade-verdict ${verdictClass(trade.verdict)}`}>
        <p className="trade-verdict-label">{t("trade_verdict")}</p>
        <h2>{t(verdictLabelKey(trade.verdict))}</h2>
        <p>
          {t("trade_net_spot", {
            value: formatMoney(trade.net_spot_usd),
            pct: formatChange(trade.net_spot_pct),
          })}
        </p>
        <p>
          {t("trade_net_ai", {
            value: formatMoney(trade.net_fair_usd),
            pct: formatChange(trade.net_fair_pct),
          })}
        </p>
        <p className="lot-meta">
          {t("trade_band_note", { n: trade.fair_band_pct })}
        </p>
      </div>

      <footer className="trade-share-card-foot">
        <div className="trade-share-card-foot-copy">
          <span>{t("trade_export_watermark")}</span>
          <span className="trade-share-card-pro">{t("trade_share_pro_cta")}</span>
        </div>
        {shareUrl ? <span className="trade-share-card-url">{shareUrl}</span> : null}
      </footer>
    </div>
  );
});
