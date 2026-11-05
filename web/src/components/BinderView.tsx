"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useTransition,
} from "react";

import { useAuth } from "@/components/AuthProvider";
import { BinderReportExport } from "@/components/BinderReportExport";
import { useLocale } from "@/components/LocaleProvider";
import { fetchBinder, fetchBinderSets, formatMoney } from "@/lib/api";
import type { BinderMissingCard, BinderResponse, BinderSetSummary } from "@/lib/types";

function MissingRow({ card }: { card: BinderMissingCard }) {
  const meta = [card.number ? `#${card.number}` : null, card.rarity]
    .filter(Boolean)
    .join(" · ");
  return (
    <Link href={`/cards/${encodeURIComponent(card.id)}`} className="scan-row">
      <div className="scan-art">
        <Image
          src={card.image_url || "/kestrel-logo.png"}
          alt={card.name}
          width={48}
          height={67}
        />
      </div>
      <div>
        <div className="lot-name">{card.name}</div>
        {meta ? <div className="lot-meta">{meta}</div> : null}
      </div>
      <div className="scan-metrics">
        <strong>{formatMoney(card.price)}</strong>
      </div>
    </Link>
  );
}

function SetProgress({ pct }: { pct: number }) {
  const width = Math.max(0, Math.min(100, pct));
  return (
    <div className="binder-progress" aria-hidden>
      <span style={{ width: `${width}%` }} />
    </div>
  );
}

export function BinderView() {
  const { t } = useLocale();
  const { user, loading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const setBoot = useRef<string | null | undefined>(undefined);
  const [sets, setSets] = useState<BinderSetSummary[]>([]);
  const [source, setSource] = useState<"supabase" | "demo" | "empty">("empty");
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<BinderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (setBoot.current !== undefined) return;
    const raw = searchParams.get("set");
    setBoot.current = raw && raw.trim() ? raw.trim() : null;
  }, [searchParams]);

  const loadSets = useCallback(() => {
    startTransition(async () => {
      try {
        const next = await fetchBinderSets();
        setSets(next.sets);
        setSource(next.source);
        setError(null);
        setSelected((prev) => {
          const boot = setBoot.current;
          if (boot && next.sets.some((s) => s.set_name === boot)) {
            setBoot.current = null;
            return boot;
          }
          if (prev && next.sets.some((s) => s.set_name === prev)) return prev;
          return next.sets[0]?.set_name || "";
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : t("binder_load_error"));
      }
    });
  }, [t]);

  const loadDetail = useCallback(
    (setName: string) => {
      if (!setName) {
        setDetail(null);
        return;
      }
      startTransition(async () => {
        try {
          const next = await fetchBinder({ set_name: setName, missing_limit: 120 });
          setDetail(next);
          setError(null);
        } catch (err) {
          setDetail(null);
          setError(err instanceof Error ? err.message : t("binder_load_error"));
        }
      });
    },
    [t],
  );

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || !user) return;
    loadSets();
  }, [hydrated, user, loadSets]);

  useEffect(() => {
    if (!hydrated || !user || !selected) return;
    loadDetail(selected);
  }, [hydrated, user, selected, loadDetail]);

  if (authLoading) {
    return (
      <section className="scanner-page binder-page">
        <p className="explore-lede">{t("binder_loading")}</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="scanner-page binder-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("binder_eyebrow")}</p>
          <h1 className="explore-title">{t("binder_title")}</h1>
          <p className="explore-lede">{t("binder_signin_lede")}</p>
        </div>
        <Link href="/portfolio" className="btn-primary">
          {t("auth_sign_in")}
        </Link>
      </section>
    );
  }

  const summary = sets.find((s) => s.set_name === selected) || null;
  const snapshot =
    detail || summary
      ? {
          set_name: detail?.set_name ?? summary?.set_name ?? selected,
          pct: detail?.pct_complete ?? summary?.pct ?? 0,
          owned: detail?.owned ?? summary?.owned ?? 0,
          total: detail?.total ?? summary?.total ?? 0,
          missing: detail?.missing ?? summary?.missing ?? 0,
          missing_cost: detail?.missing_cost ?? summary?.missing_cost ?? 0,
          missing_unpriced: detail?.missing_unpriced ?? 0,
        }
      : null;

  return (
    <section className="scanner-page binder-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("binder_eyebrow")}</p>
        <h1 className="explore-title">{t("binder_title")}</h1>
        <p className="explore-lede">
          {t("binder_lede")}
          {source === "demo" ? ` · ${t("explore_demo")}` : ""}
        </p>
      </div>

      {error ? <p className="banner-error">{error}</p> : null}

      <div className="filter-row binder-filters">
        <label>
          <span>{t("binder_set")}</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            disabled={pending || sets.length === 0}
          >
            {sets.length === 0 ? (
              <option value="">{t("binder_no_sets")}</option>
            ) : (
              sets.map((row) => (
                <option key={row.set_name} value={row.set_name}>
                  {row.set_name} · {row.pct.toFixed(0)}%
                </option>
              ))
            )}
          </select>
        </label>
      </div>

      {snapshot ? (
        <div className="kpi-row binder-kpis">
          <div className="kpi-chip">
            <span>{t("binder_kpi_complete")}</span>
            <strong>{snapshot.pct.toFixed(1)}%</strong>
            <SetProgress pct={snapshot.pct} />
          </div>
          <div className="kpi-chip">
            <span>{t("binder_kpi_owned")}</span>
            <strong>
              {t("binder_owned_of", {
                owned: snapshot.owned,
                total: snapshot.total,
              })}
            </strong>
          </div>
          <div className="kpi-chip">
            <span>{t("binder_kpi_missing")}</span>
            <strong>{snapshot.missing}</strong>
          </div>
          <div className="kpi-chip">
            <span>{t("binder_kpi_cost")}</span>
            <strong>{formatMoney(snapshot.missing_cost)}</strong>
            {(snapshot.missing_unpriced ?? 0) > 0 ? (
              <span className="lot-meta">
                {t("binder_unpriced", { n: snapshot.missing_unpriced ?? 0 })}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      {snapshot ? <BinderReportExport snapshot={snapshot} /> : null}

      <div className="binder-panels">
        <div>
          <h2 className="section-title">
            {t("binder_missing_title", { n: detail?.missing ?? 0 })}
          </h2>
          {pending && !detail ? (
            <p className="explore-lede">{t("binder_loading")}</p>
          ) : null}
          {detail && detail.missing_cards.length === 0 ? (
            <p className="empty-state">{t("binder_complete")}</p>
          ) : null}
          {detail && detail.missing_cards.length > 0 ? (
            <div className="scan-list">
              {detail.missing_cards.map((card) => (
                <MissingRow key={card.id} card={card} />
              ))}
            </div>
          ) : null}
          {detail && detail.missing > detail.missing_cards.length ? (
            <p className="lot-meta">
              {t("binder_missing_truncated", {
                shown: detail.missing_cards.length,
                total: detail.missing,
              })}
            </p>
          ) : null}
        </div>

        {sets.length > 0 ? (
          <aside className="binder-set-list" aria-label={t("binder_all_sets")}>
            <h2 className="section-title">{t("binder_all_sets")}</h2>
            <ul>
              {sets.map((row) => (
                <li key={row.set_name}>
                  <button
                    type="button"
                    className={
                      row.set_name === selected
                        ? "binder-set-btn is-active"
                        : "binder-set-btn"
                    }
                    onClick={() => setSelected(row.set_name)}
                  >
                    <span className="binder-set-name">{row.set_name}</span>
                    <span className="binder-set-meta">
                      {row.pct.toFixed(0)}% · {formatMoney(row.missing_cost)}
                    </span>
                    <SetProgress pct={row.pct} />
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        ) : null}
      </div>
    </section>
  );
}
