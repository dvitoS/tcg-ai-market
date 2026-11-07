"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import { addPortfolioLot } from "@/lib/api";
import {
  PRINTINGS,
  RAW_CONDITIONS,
  adjustNmPrice,
  normalizeCondition,
  normalizePrinting,
} from "@/lib/lotPriceAdjust";

export function AddLotForm({
  cardId,
  cardName,
  defaultPrice,
}: {
  cardId: string;
  cardName: string;
  defaultPrice?: number | null;
}) {
  const { user } = useAuth();
  const { t } = useLocale();
  const [qty, setQty] = useState(1);
  const [price, setPrice] = useState(
    defaultPrice != null && Number.isFinite(defaultPrice) ? Number(defaultPrice) : 0,
  );
  const [condition, setCondition] = useState("NM");
  const [printing, setPrinting] = useState("Normal");
  const [grade, setGrade] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const adjustedHint = adjustNmPrice(defaultPrice, { condition, printing });

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!user) return;
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await addPortfolioLot({
        card_id: cardId,
        quantity: Math.max(1, Math.floor(qty) || 1),
        purchase_price: Number(price),
        condition: normalizeCondition(condition),
        printing: normalizePrinting(printing),
        grade: grade.trim() || null,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add lot");
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <section className="add-lot-panel">
        <h2>{t("add_lot_title")}</h2>
        <p className="add-lot-hint">
          {t("add_lot_guest", { name: cardName })}{" "}
          <Link href="/signin?next=/portfolio" className="inline-link">
            {t("add_lot_open")}
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section className="add-lot-panel">
      <h2>{t("add_lot_title")}</h2>
      <p className="add-lot-hint">{t("add_lot_hint")}</p>
      <form className="add-lot-form" onSubmit={onSubmit}>
        <label>
          <span>{t("add_lot_qty")}</span>
          <input
            type="number"
            min={1}
            step={1}
            value={qty}
            onChange={(e) => setQty(Number(e.target.value) || 1)}
            required
          />
        </label>
        <label>
          <span>{t("add_lot_cost")}</span>
          <input
            type="number"
            min={0.01}
            step={0.01}
            value={price}
            onChange={(e) => setPrice(Number(e.target.value) || 0)}
            required
          />
        </label>
        <label>
          <span>{t("port_condition")}</span>
          <select value={condition} onChange={(e) => setCondition(e.target.value)}>
            {RAW_CONDITIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("port_printing")}</span>
          <select value={printing} onChange={(e) => setPrinting(e.target.value)}>
            {PRINTINGS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("add_lot_grade")}</span>
          <input
            type="text"
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
            placeholder={t("add_lot_optional")}
          />
        </label>
        <button type="submit" className="btn-primary" disabled={busy || price <= 0}>
          {busy ? t("add_lot_busy") : t("add_lot_submit")}
        </button>
      </form>
      {adjustedHint != null && (condition !== "NM" || printing !== "Normal") ? (
        <p className="lot-meta add-lot-adjust-hint">
          {t("port_adjust_hint", {
            value: adjustedHint.toFixed(2),
            factor: (
              defaultPrice && Number(defaultPrice) > 0
                ? adjustedHint / Number(defaultPrice)
                : 1
            ).toFixed(2),
          })}
        </p>
      ) : null}
      {error ? <p className="banner-error">{error}</p> : null}
      {done ? (
        <p className="add-lot-ok">
          {t("add_lot_done")}{" "}
          <Link href="/portfolio" className="inline-link">
            {t("add_lot_view")}
          </Link>
        </p>
      ) : null}
    </section>
  );
}
