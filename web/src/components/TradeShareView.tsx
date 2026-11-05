"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { TradeReportExport } from "@/components/TradeReportExport";
import { fetchTradeShare, formatChange, formatMoney } from "@/lib/api";
import type { TradeShareView as TradeSharePayload, TradeSide } from "@/lib/types";

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

function ReadOnlySide({ title, side }: { title: string; side: TradeSide }) {
  const { t } = useLocale();
  return (
    <div className="trade-side">
      <div className="trade-side-head">
        <h2>{title}</h2>
        <p className="lot-meta">
          {formatMoney(side.spot_total)} spot · {formatMoney(side.fair_total)} AI
        </p>
      </div>
      <div className="trade-lines">
        {side.lines.length === 0 ? (
          <p className="explore-lede">{t("trade_share_empty_side")}</p>
        ) : (
          side.lines.map((line) => (
            <div key={`${line.card_id}-${line.quantity}`} className="trade-line">
              <div className="scan-art">
                <Image
                  src={line.image_url || "/kestrel-logo.png"}
                  alt={line.name || line.card_id}
                  width={40}
                  height={56}
                />
              </div>
              <div>
                {line.matched && line.card_id ? (
                  <Link href={`/cards/${line.card_id}`} className="lot-name">
                    {line.name || line.card_id}
                  </Link>
                ) : (
                  <div className="lot-name">{line.name || line.card_id}</div>
                )}
                <div className="lot-meta">
                  ×{line.quantity}
                  {line.spot != null ? ` · ${formatMoney(line.spot)}` : ""}
                  {line.expected_change_pct != null
                    ? ` · AI ${formatChange(line.expected_change_pct)}`
                    : ""}
                  {!line.matched ? ` · ${t("trade_share_unmatched")}` : ""}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export function TradeShareView({ shareId }: { shareId: string }) {
  const { t } = useLocale();
  const [data, setData] = useState<TradeSharePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState(`/trade/s/${shareId}`);

  useEffect(() => {
    setShareUrl(`${window.location.origin}/trade/s/${shareId}`);
  }, [shareId]);

  useEffect(() => {
    let alive = true;
    setError(null);
    void fetchTradeShare(shareId)
      .then((payload) => {
        if (!alive) return;
        setData(payload);
      })
      .catch((err) => {
        if (!alive) return;
        setData(null);
        setError(err instanceof Error ? err.message : t("trade_share_error"));
      });
    return () => {
      alive = false;
    };
  }, [shareId, t]);

  if (error) {
    return (
      <section className="scanner-page trade-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("trade_share_eyebrow")}</p>
          <h1 className="explore-title">{t("trade_share_missing")}</h1>
          <p className="explore-lede">{error}</p>
        </div>
        <Link href="/trade" className="btn-primary">
          {t("trade_share_open_analyzer")}
        </Link>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="scanner-page trade-page">
        <p className="explore-lede">{t("trade_share_loading")}</p>
      </section>
    );
  }

  return (
    <section className="scanner-page trade-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("trade_share_eyebrow")}</p>
        <h1 className="explore-title">{t("trade_share_title")}</h1>
        <p className="explore-lede">{t("trade_share_lede")}</p>
      </div>

      <div className="trade-board">
        <ReadOnlySide title={t("trade_you_give")} side={data.you} />
        <ReadOnlySide title={t("trade_them_give")} side={data.them} />
      </div>

      <div className={`trade-verdict ${verdictClass(data.verdict)}`}>
        <p className="trade-verdict-label">{t("trade_verdict")}</p>
        <h2>{t(verdictLabelKey(data.verdict))}</h2>
        <p className="explore-lede">
          {t("trade_net_spot", {
            value: formatMoney(data.net_spot_usd),
            pct: formatChange(data.net_spot_pct),
          })}
        </p>
        <p className="explore-lede">
          {t("trade_net_ai", {
            value: formatMoney(data.net_fair_usd),
            pct: formatChange(data.net_fair_pct),
          })}
        </p>
        <p className="lot-meta">
          {t("trade_band_note", { n: data.fair_band_pct })}
          {data.source === "demo" ? ` · ${t("explore_demo")}` : ""}
          {` · ${t("trade_share_live")}`}
        </p>
      </div>

      <div className="detail-actions">
        <Link href="/trade" className="btn-primary">
          {t("trade_share_open_analyzer")}
        </Link>
        {data.checkout_url ? (
          <a href={data.checkout_url} className="btn-ghost">
            {t("dealer_upgrade")}
          </a>
        ) : (
          <Link href="/pro" className="btn-ghost">
            {t("trade_share_pro_cta")}
          </Link>
        )}
      </div>

      <TradeReportExport trade={data} shareUrl={shareUrl} />
    </section>
  );
}
