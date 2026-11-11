"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useCurrency } from "@/components/CurrencyProvider";
import { HoloCardArt } from "@/components/HoloCardArt";
import { useLocale } from "@/components/LocaleProvider";
import { addPortfolioLot, ensureSealedCard, formatMoney } from "@/lib/api";
import { resolveCardImageUrl } from "@/lib/cardImage";
import { resolveFoilMode } from "@/lib/foilMode";
import type { CatalogCard, SealedDetailResponse, SealedQuoteItem } from "@/lib/types";

function moneyShort(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

function cardSpot(card: CatalogCard): number | null {
  const raw = card.market_price ?? card.price;
  if (raw == null || !Number.isFinite(Number(raw))) return null;
  return Number(raw);
}

/** Stable USD for SSR + first paint — avoids currency/locale hydrate mismatch (#418). */
function usdSpot(value?: number | null): string {
  return formatMoney(value, "USD");
}

function HitTile({
  card,
  compact = false,
}: {
  card: CatalogCard;
  /** SIR strip — ~40% smaller than the IR hit grid tiles. */
  compact?: boolean;
}) {
  const foil = resolveFoilMode(card.finishes, card.rarity, card.name);
  const image = resolveCardImageUrl(card.id, card.image_url);
  return (
    <Link
      href={`/cards/${encodeURIComponent(card.id)}`}
      className={`sealed-hit-tile${compact ? " is-compact" : ""}`}
    >
      <HoloCardArt
        cardId={card.id}
        name={card.name}
        image={image}
        foil={foil}
        width={compact ? 110 : 160}
        height={compact ? 154 : 224}
        sizes={
          compact
            ? "(max-width: 720px) 20vw, 88px"
            : "(max-width: 720px) 28vw, 120px"
        }
        className="sealed-hit-holo"
      />
      <span className="sealed-hit-price" suppressHydrationWarning>
        {usdSpot(cardSpot(card))}
      </span>
      <span className="sealed-hit-name">{card.name}</span>
    </Link>
  );
}

function productBlurb(
  product: SealedQuoteItem,
  t: (key: "sealed_detail_blurb_box_1" | "sealed_detail_blurb_box_2" | "sealed_detail_blurb_box_3" | "sealed_detail_blurb_etb_1" | "sealed_detail_blurb_etb_2" | "sealed_detail_blurb_bundle_1" | "sealed_detail_blurb_bundle_2" | "sealed_detail_blurb_generic") => string,
): string[] {
  const packs = product.packs;
  const kind = product.product_kind || "";
  if (kind === "booster_box" || packs === 36) {
    return [
      t("sealed_detail_blurb_box_1"),
      t("sealed_detail_blurb_box_2"),
      t("sealed_detail_blurb_box_3"),
    ];
  }
  if (kind === "etb") {
    return [t("sealed_detail_blurb_etb_1"), t("sealed_detail_blurb_etb_2")];
  }
  if (kind === "bundle") {
    return [t("sealed_detail_blurb_bundle_1"), t("sealed_detail_blurb_bundle_2")];
  }
  return [t("sealed_detail_blurb_generic")];
}

export function SealedDetailView({ detail }: { detail: SealedDetailResponse }) {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const { user, loading: authLoading } = useAuth();
  const product = detail.product;
  const setName = detail.set_name || product.set_name || "";
  const ir = detail.groups.find((g) => g.key === "ir");
  const sir = detail.groups.find((g) => g.key === "sir");
  const irHits = detail.hits.filter((c) =>
    String(c.rarity || "")
      .toLowerCase()
      .includes("illustration rare") &&
      !String(c.rarity || "")
        .toLowerCase()
        .includes("special"),
  );
  const gridHits = irHits.length >= 6 ? irHits : detail.hits;
  const [qty, setQty] = useState(1);
  const [cost, setCost] = useState(
    product.spot_usd != null && Number.isFinite(Number(product.spot_usd))
      ? Number(product.spot_usd)
      : 0,
  );
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [spotReady, setSpotReady] = useState(false);

  useEffect(() => {
    setSpotReady(true);
  }, []);

  const productSpot = spotReady
    ? formatSpot(product.spot_usd)
    : usdSpot(product.spot_usd);

  async function onAdd(event: FormEvent) {
    event.preventDefault();
    if (!user) return;
    if (!(Number(cost) > 0)) {
      setError(t("sealed_need_cost"));
      return;
    }
    setPending(true);
    setError(null);
    setNote(null);
    try {
      const ensured = await ensureSealedCard(product);
      await addPortfolioLot({
        card_id: ensured.card_id,
        quantity: Math.max(1, Math.floor(qty) || 1),
        purchase_price: Number(cost),
        condition: "NM",
        printing: "Normal",
      });
      setNote(t("sealed_added", { name: ensured.name }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("sealed_error"));
    } finally {
      setPending(false);
    }
  }

  const summary = detail.summary;
  const blurbs = productBlurb(product, t);

  return (
    <section className="sealed-detail">
      <div className="sealed-detail-top">
        <Link href="/sealed" className="sealed-detail-back">
          ← {t("sealed_detail_back")}
        </Link>
        <div className="sealed-detail-title-row">
          <div className="sealed-detail-title-copy">
            <p className="sealed-detail-eyebrow">
              {[setName, t("sealed_detail_vs")].filter(Boolean).join(" · ")}
            </p>
            <h1 className="sealed-detail-title">{t("sealed_detail_title")}</h1>
          </div>
          {!authLoading ? (
            user ? (
              <form
                id="sealed-detail-add"
                className="sealed-detail-lot-inline"
                onSubmit={onAdd}
              >
                <label className="sealed-detail-lot-field">
                  <span>{t("add_lot_qty")}</span>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={qty}
                    onChange={(e) => setQty(Number(e.target.value) || 1)}
                    aria-label={t("add_lot_qty")}
                  />
                </label>
                <label className="sealed-detail-lot-field sealed-detail-lot-cost">
                  <span>{t("add_lot_cost")}</span>
                  <input
                    type="number"
                    min={0.01}
                    step={0.01}
                    value={cost}
                    onChange={(e) => setCost(Number(e.target.value) || 0)}
                    aria-label={t("add_lot_cost")}
                  />
                </label>
                <button
                  type="submit"
                  className="sealed-detail-add-btn"
                  disabled={pending}
                >
                  {t("sealed_desk_add_lot")}
                </button>
              </form>
            ) : (
              <Link
                href={`/signin?next=${encodeURIComponent(`/sealed/${product.tcgplayer_id || ""}`)}`}
                className="sealed-detail-add-btn"
              >
                {t("sealed_desk_signin")}
              </Link>
            )
          ) : null}
        </div>
      </div>

      <div className="sealed-detail-split">
        <article className="sealed-detail-product">
          <p className="sealed-detail-kicker">{product.name}</p>
          <p className="sealed-detail-price" suppressHydrationWarning>
            {productSpot}
          </p>
          <p className="sealed-detail-price-meta">
            {t("sealed_detail_market")}
            {product.packs ? ` · ${t("sealed_detail_packs", { n: product.packs })}` : ""}
          </p>
          <div className="sealed-detail-art">
            <Image
              src={product.image_url || "/kestrel-logo.png"}
              alt={product.name}
              width={420}
              height={420}
              className="sealed-detail-img"
              priority
              sizes="(max-width: 720px) 70vw, 320px"
            />
          </div>
          <div className="sealed-detail-blurb">
            <p className="sealed-detail-blurb-title">{t("sealed_detail_what")}</p>
            <ul>
              {blurbs.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          {detail.shelf.length > 0 ? (
            <div className="sealed-detail-shelf">
              <p className="sealed-detail-shelf-title">{t("sealed_detail_shelf")}</p>
              <ul>
                {detail.shelf.map((row) => (
                  <li key={row.card_id}>
                    <Link href={`/sealed/${encodeURIComponent(row.tcgplayer_id || "")}`}>
                      <span>{row.name}</span>
                      <strong suppressHydrationWarning>
                        {spotReady ? formatSpot(row.spot_usd) : usdSpot(row.spot_usd)}
                      </strong>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </article>

        <article className="sealed-detail-hits">
          <p className="sealed-detail-kicker">
            {ir
              ? t("sealed_detail_ir_kicker", { n: ir.count })
              : t("sealed_detail_hits_kicker", { set: setName || "—" })}
          </p>
          <p className="sealed-detail-price" suppressHydrationWarning>
            {ir ? moneyShort(ir.total_usd) : "—"}
          </p>
          <p className="sealed-detail-price-meta">
            {ir
              ? t("sealed_detail_ir_meta", { n: ir.count })
              : t("sealed_detail_hits_meta")}
          </p>
          {gridHits.length === 0 ? (
            <p className="lot-meta">{t("sealed_detail_hits_empty")}</p>
          ) : (
            <div className="sealed-hit-grid">
              {gridHits.slice(0, 24).map((card) => (
                <HitTile key={card.id} card={card} />
              ))}
            </div>
          )}
        </article>
      </div>

      {sir ? (
        <section className="sealed-detail-sir">
          <div className="sealed-detail-sir-head">
            <h2>
              {t("sealed_detail_sir_title", {
                n: sir.count,
                total: moneyShort(sir.total_usd),
              })}
            </h2>
          </div>
          <div className="sealed-sir-grid">
            {(sir.featured.length ? sir.featured : detail.hits.slice(0, 3)).map(
              (card) => (
                <HitTile key={`sir-${card.id}`} card={card} compact />
              ),
            )}
          </div>
        </section>
      ) : null}

      {summary?.ir_vs_product_usd != null ? (
        <p className="sealed-detail-summary">
          {summary.ir_vs_product_usd >= 0
            ? t("sealed_detail_summary_ir_less", {
                delta: moneyShort(summary.ir_vs_product_usd),
              })
            : t("sealed_detail_summary_ir_more", {
                delta: moneyShort(Math.abs(summary.ir_vs_product_usd)),
              })}
          {summary.sir_boxes != null
            ? ` ${t("sealed_detail_summary_sir_boxes", { n: summary.sir_boxes })}`
            : ""}
        </p>
      ) : null}

      {error ? <p className="banner-error">{error}</p> : null}
      {note ? <p className="banner-ok">{note}</p> : null}
    </section>
  );
}
