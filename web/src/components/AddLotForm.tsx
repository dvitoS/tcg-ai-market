"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { addPortfolioLot } from "@/lib/api";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG", "PSA 10", "PSA 9", "Other"];

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
  const [qty, setQty] = useState(1);
  const [price, setPrice] = useState(
    defaultPrice != null && Number.isFinite(defaultPrice) ? Number(defaultPrice) : 0,
  );
  const [condition, setCondition] = useState("NM");
  const [grade, setGrade] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

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
        condition,
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
        <h2>Add to portfolio</h2>
        <p className="add-lot-hint">
          Sign in to log a lot for {cardName}.{" "}
          <Link href="/portfolio" className="inline-link">
            Open portfolio
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section className="add-lot-panel">
      <h2>Add to portfolio</h2>
      <p className="add-lot-hint">Log quantity and cost basis for this card.</p>
      <form className="add-lot-form" onSubmit={onSubmit}>
        <label>
          <span>Qty</span>
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
          <span>Cost (USD)</span>
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
          <span>Condition</span>
          <select value={condition} onChange={(e) => setCondition(e.target.value)}>
            {CONDITIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Grade</span>
          <input
            type="text"
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
            placeholder="Optional"
          />
        </label>
        <button type="submit" className="btn-primary" disabled={busy || price <= 0}>
          {busy ? "Adding…" : "Add lot"}
        </button>
      </form>
      {error ? <p className="banner-error">{error}</p> : null}
      {done ? (
        <p className="add-lot-ok">
          Added.{" "}
          <Link href="/portfolio" className="inline-link">
            View portfolio
          </Link>
        </p>
      ) : null}
    </section>
  );
}
