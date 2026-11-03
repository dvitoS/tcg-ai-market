import Image from "next/image";
import Link from "next/link";

import { PriceChart } from "@/components/PriceChart";
import { WatchToggle } from "@/components/WatchToggle";
import { formatChange, formatMoney } from "@/lib/api";
import type { CardDetailResponse, HistoryPoint } from "@/lib/types";

function deltaClass(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "flat";
  if (value > 0.05) return "up";
  if (value < -0.05) return "down";
  return "flat";
}

function signalClass(signal?: string | null): string {
  const key = (signal || "").toUpperCase();
  if (key === "BUY") return "signal-buy";
  if (key === "SELL") return "signal-sell";
  return "signal-hold";
}

export function CardDetailView({
  detail,
  points,
}: {
  detail: CardDetailResponse;
  points: HistoryPoint[];
}) {
  const { card, pred_lo_pct, pred_hi_pct } = detail;
  const prices = points.map((p) => p.price).filter((n) => Number.isFinite(n));
  const fromPoints = {
    points: points.length,
    min_price: prices.length ? Math.min(...prices) : null,
    max_price: prices.length ? Math.max(...prices) : null,
    last_price: prices.length ? prices[prices.length - 1] : card.price ?? null,
    previous_price: prices.length > 1 ? prices[prices.length - 2] : null,
    day_change_pct:
      prices.length > 1 && prices[prices.length - 2]
        ? ((prices[prices.length - 1] - prices[prices.length - 2]) /
            prices[prices.length - 2]) *
          100
        : null,
    first_date: points[0]?.date ?? null,
    last_date: points[points.length - 1]?.date ?? null,
  };
  const history = {
    ...fromPoints,
    ...(detail.history || {}),
    min_price: detail.history?.min_price ?? fromPoints.min_price,
    max_price: detail.history?.max_price ?? fromPoints.max_price,
    last_price: detail.history?.last_price ?? fromPoints.last_price,
    day_change_pct: detail.history?.day_change_pct ?? fromPoints.day_change_pct,
    points: detail.history?.points || fromPoints.points,
  };
  const meta = [card.set_name, card.rarity, card.id].filter(Boolean).join(" · ");
  const image = card.image_url || "/kestrel-logo.png";
  const dayChange = history.day_change_pct;
  const showSignal = Boolean(card.confidence_ok && card.conformal_ok && card.signal);
  const band =
    pred_lo_pct != null && pred_hi_pct != null
      ? `${formatChange(pred_lo_pct, 1)} … ${formatChange(pred_hi_pct, 1)}`
      : null;

  return (
    <article className="detail-page">
      <Link href="/" className="detail-back">
        ← Back to browse
      </Link>

      <div className="detail-layout">
        <div className="detail-main">
          <section className="detail-hero-card">
            <div className="detail-hero-art">
              <Image
                src={image}
                alt={card.name}
                width={420}
                height={586}
                priority
                className="detail-hero-img"
              />
            </div>
            <div className="detail-hero-copy">
              <p className="detail-kicker">Card detail</p>
              <h1 className="detail-name">{card.name}</h1>
              <p className="detail-meta">{meta}</p>
              <div className="detail-price">
                {formatMoney(history.last_price ?? card.price, "USD", 2)}
              </div>
              <div className={`detail-hero-delta ${deltaClass(dayChange)}`}>
                {formatChange(dayChange, 2)}
                {showSignal ? ` · ${card.signal}` : ""}
              </div>
              <div className="detail-actions">
                <WatchToggle cardId={card.id} />
                <Link href="/portfolio#watchlist" className="btn-ghost">
                  Open watchlist
                </Link>
              </div>
              <div className="stat-row">
                <div className="stat-chip">
                  <span>Range min</span>
                  <strong>{formatMoney(history.min_price, "USD", 2)}</strong>
                </div>
                <div className="stat-chip">
                  <span>Range max</span>
                  <strong>{formatMoney(history.max_price, "USD", 2)}</strong>
                </div>
                <div className="stat-chip">
                  <span>Points</span>
                  <strong>{history.points || points.length || "—"}</strong>
                </div>
              </div>
            </div>
          </section>

          <section className="detail-ai-board">
            <div className="detail-ai-head">
              <h2>AI prediction</h2>
            </div>
            <p className="ai-move-label">Expected move</p>
            <p className={`ai-move-value ${deltaClass(card.expected_change_pct)}`}>
              {formatChange(card.expected_change_pct, 2)}
            </p>
            <p className="ai-board-price-label">Predicted price</p>
            <p className="ai-board-price">
              {formatMoney(card.predicted_price, "USD", 2)}
              {card.expected_change_pct != null ? (
                <span className="ai-board-delta">
                  {formatChange(card.expected_change_pct, 2)}
                </span>
              ) : null}
            </p>
            {band ? (
              <p className="ai-board-caption">Conformal band {band}</p>
            ) : (
              <p className="ai-board-caption">Horizon forecast from the market board.</p>
            )}
            {showSignal ? (
              <div className={`signal-chip ${signalClass(card.signal)}`}>{card.signal}</div>
            ) : (
              <div className="ai-low-conf">Low confidence — treat as HOLD until more data lands.</div>
            )}
          </section>
        </div>

        <aside className="detail-side">
          <PriceChart points={points} predictedPrice={card.predicted_price} />
        </aside>
      </div>
    </article>
  );
}
