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
import { DeskLoading } from "@/components/DeskLoading";
import { useLocale } from "@/components/LocaleProvider";
import { fetchBinder, fetchBinderSets, formatMoney } from "@/lib/api";
import { cleanBinderShareSet } from "@/lib/binderExport";
import { onCardImageError, resolveCardImageUrl } from "@/lib/cardImage";
import type { BinderMissingCard, BinderResponse, BinderSetSummary } from "@/lib/types";

type MissingView = "grid" | "list";

function MissingCardTile({ card }: { card: BinderMissingCard }) {
  const meta = [card.number ? `#${card.number}` : null, card.rarity]
    .filter(Boolean)
    .join(" · ");
  return (
    <Link
      href={`/cards/${encodeURIComponent(card.id)}`}
      className="binder-missing-tile"
    >
      <span className="binder-missing-art">
        <Image
          src={resolveCardImageUrl(card.id, card.image_url)}
          alt={card.name}
          width={180}
          height={252}
          sizes="(max-width: 720px) 42vw, 140px"
          onError={(event) => onCardImageError(event, card.id)}
        />
      </span>
      <span className="binder-missing-body">
        <span className="lot-name">{card.name}</span>
        {meta ? <span className="lot-meta">{meta}</span> : null}
        <span className="binder-missing-price">
          {card.price != null ? formatMoney(card.price) : "—"}
        </span>
      </span>
    </Link>
  );
}

function MissingRow({ card }: { card: BinderMissingCard }) {
  const meta = [card.number ? `#${card.number}` : null, card.rarity]
    .filter(Boolean)
    .join(" · ");
  return (
    <Link href={`/cards/${encodeURIComponent(card.id)}`} className="scan-row">
      <div className="scan-art">
        <Image
          src={resolveCardImageUrl(card.id, card.image_url)}
          alt={card.name}
          width={48}
          height={67}
          onError={(event) => onCardImageError(event, card.id)}
        />
      </div>
      <div>
        <div className="lot-name">{card.name}</div>
        {meta ? <div className="lot-meta">{meta}</div> : null}
      </div>
      <div className="scan-metrics">
        <strong>{card.price != null ? formatMoney(card.price) : "—"}</strong>
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
  const [booted, setBooted] = useState(false);
  const [missingView, setMissingView] = useState<MissingView>("grid");

  const [sharedSet, setSharedSet] = useState<string | null>(null);

  useEffect(() => {
    if (setBoot.current !== undefined) return;
    const boot = cleanBinderShareSet(searchParams.get("set"));
    setBoot.current = boot;
    setSharedSet(boot);
  }, [searchParams]);

  const loadSets = useCallback(() => {
    startTransition(async () => {
      try {
        const boot = setBoot.current;
        // When share/deeplink already names a set, fetch sets + detail together.
        const [next, detailBoot] = await Promise.all([
          fetchBinderSets(),
          boot
            ? fetchBinder({ set_name: boot, missing_limit: 120 }).catch(() => null)
            : Promise.resolve(null),
        ]);
        setSets(next.sets);
        setSource(next.source);
        setError(null);
        setSelected((prev) => {
          if (boot && next.sets.some((s) => s.set_name === boot)) {
            setBoot.current = null;
            return boot;
          }
          if (prev && next.sets.some((s) => s.set_name === prev)) return prev;
          return next.sets[0]?.set_name || "";
        });
        if (detailBoot && boot && detailBoot.set_name === boot) {
          setDetail(detailBoot);
        }
        setBooted(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("binder_load_error"));
        setBooted(true);
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
    if (!user) {
      setBooted(false);
      return;
    }
    if (!hydrated) return;
    loadSets();
  }, [hydrated, user, loadSets]);

  useEffect(() => {
    if (!hydrated || !user || !selected) return;
    // Skip duplicate detail fetch when boot already hydrated this set.
    if (detail?.set_name === selected) return;
    loadDetail(selected);
  }, [hydrated, user, selected, loadDetail, detail?.set_name]);

  if (authLoading || (user && !booted)) {
    return (
      <section className="scanner-page binder-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("binder_eyebrow")}</p>
          <h1 className="explore-title">{t("binder_title")}</h1>
        </div>
        <DeskLoading label={t("binder_loading")} variant="panel" skeletonCount={6} />
      </section>
    );
  }

  if (!user) {
    const next = sharedSet
      ? `/signin?next=${encodeURIComponent(`/binder?set=${encodeURIComponent(sharedSet)}`)}`
      : "/signin?next=/binder";
    return (
      <section className="scanner-page binder-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("binder_eyebrow")}</p>
          <h1 className="explore-title">{t("binder_title")}</h1>
          <p className="explore-lede">{t("binder_signin_lede")}</p>
        </div>
        {sharedSet ? (
          <div className="binder-share-preview">
            <p className="explore-command-eyebrow">
              {t("binder_share_preview_title")}
            </p>
            <p className="binder-share-preview-set">{sharedSet}</p>
            <p className="explore-lede">{t("binder_share_preview_lede")}</p>
          </div>
        ) : null}
        <Link href={next} className="btn-primary">
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

      {snapshot ? <BinderReportExport snapshot={snapshot} /> : null}

      {error ? <p className="banner-error">{error}</p> : null}
      {pending ? <DeskLoading label={t("explore_updating")} variant="banner" /> : null}

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
                  {row.set_name} · {row.owned}/{row.total}
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

      <div className="detail-desk-split binder-panels">
        <div className="detail-desk-main">
          <div className="portfolio-section-head">
            <h2>{t("binder_missing_title", { n: detail?.missing ?? 0 })}</h2>
            {detail && detail.missing_cards.length > 0 ? (
              <div className="mode-toggle binder-view-toggle" role="group">
                <button
                  type="button"
                  className={missingView === "grid" ? "is-active" : undefined}
                  onClick={() => setMissingView("grid")}
                >
                  {t("binder_view_grid")}
                </button>
                <button
                  type="button"
                  className={missingView === "list" ? "is-active" : undefined}
                  onClick={() => setMissingView("list")}
                >
                  {t("binder_view_list")}
                </button>
              </div>
            ) : null}
          </div>
          {pending && !detail ? (
            <DeskLoading label={t("binder_loading")} variant="panel" skeletonCount={4} />
          ) : null}
          {detail && detail.missing_cards.length === 0 ? (
            <p className="empty-state">{t("binder_complete")}</p>
          ) : null}
          {detail && detail.missing_cards.length > 0 ? (
            missingView === "grid" ? (
              <div
                className={`binder-missing-grid${pending ? " is-pending" : ""}`}
              >
                {detail.missing_cards.map((card) => (
                  <MissingCardTile key={card.id} card={card} />
                ))}
              </div>
            ) : (
              <div className={`scan-list${pending ? " is-pending" : ""}`}>
                {detail.missing_cards.map((card) => (
                  <MissingRow key={card.id} card={card} />
                ))}
              </div>
            )
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
          <aside
            className="detail-desk-side binder-set-list"
            aria-label={t("binder_progress_title")}
          >
            <div className="detail-side-module">
              <h2 className="detail-side-heading">{t("binder_progress_title")}</h2>
              <p className="lot-meta binder-progress-lede">
                {t("binder_progress_lede")}
              </p>
              <ul className="binder-progress-list">
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
                      <span className="binder-set-head">
                        <span className="binder-set-name">{row.set_name}</span>
                        <span className="binder-set-frac">
                          {t("binder_owned_of", {
                            owned: row.owned,
                            total: row.total,
                          })}
                        </span>
                      </span>
                      <SetProgress pct={row.pct} />
                      <span className="binder-set-meta">
                        {row.pct.toFixed(0)}% · {formatMoney(row.missing_cost)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        ) : null}
      </div>
    </section>
  );
}
