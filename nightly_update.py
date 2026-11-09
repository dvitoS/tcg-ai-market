# pip install requests python-dotenv pandas xgboost scikit-learn supabase
"""Noćni radnik: katalog → PokéWallet snimke → re-trening XGBoost."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

LOG = logging.getLogger("tcg.nightly")


class _TeeStream:
    """Šalje print() i u konzolu i u automation.log."""

    def __init__(self, primary, logger: logging.Logger, level: int = logging.INFO) -> None:
        self.primary = primary
        self.logger = logger
        self.level = level
        self._buffer = ""

    def write(self, message: str) -> int:
        self.primary.write(message)
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            text = line.rstrip()
            if text:
                self.logger.log(self.level, text)
        return len(message)

    def flush(self) -> None:
        self.primary.flush()
        if self._buffer.strip():
            self.logger.log(self.level, self._buffer.rstrip())
            self._buffer = ""


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    LOG.handlers.clear()
    LOG.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOG.addHandler(file_handler)

    console = logging.StreamHandler(sys.__stdout__)
    console.setFormatter(formatter)
    LOG.addHandler(console)

    sys.stdout = _TeeStream(sys.__stdout__, LOG, logging.INFO)
    if not os.environ.get("GITHUB_ACTIONS"):
        sys.stderr = _TeeStream(sys.__stderr__, LOG, logging.ERROR)


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _report_error(phase: str, exc: BaseException) -> None:
    msg = f"{phase}: {type(exc).__name__}: {exc}"
    print(f"Nightly phase FAILED — {msg}", file=sys.__stderr__)
    traceback.print_exc(file=sys.__stderr__)
    # GitHub Actions annotation (vidljivo u Summary / Annotations).
    safe = str(exc).replace("\n", " ").replace("%", "%25")[:180]
    print(f"::error title={phase}::{type(exc).__name__}: {safe}", file=sys.__stderr__)
    try:
        LOG.exception("Faza '%s' nije uspjela: %s", phase, exc)
    except Exception:
        pass


def _catalog_mode() -> str:
    """gapfill (default) | full | skip — env NIGHTLY_CATALOG_MODE."""
    raw = os.environ.get("NIGHTLY_CATALOG_MODE", "").strip().lower()
    if raw in {"full", "all", "refresh"}:
        return "full"
    if raw in {"skip", "off", "none"}:
        return "skip"
    if raw in {"gapfill", "gap", "incremental", ""}:
        # Empty → gapfill unless legacy NIGHTLY_SKIP_CATALOG.
        if _env_flag("NIGHTLY_SKIP_CATALOG"):
            return "skip"
        return "gapfill"
    return "gapfill"


def refresh_card_catalog() -> int:
    from api_client import (
        clean_cards,
        fetch_cards,
        resolve_catalog_targets,
        select_gapfill_catalog_targets,
    )
    from config import catalog_price_floor, pokemon_tcg_api_key, rate_limit_sleep_seconds
    from main import save_cards

    mode = _catalog_mode()
    if mode == "skip":
        LOG.info("Korak 1/3: PRESKOČEN (NIGHTLY_CATALOG_MODE=skip).")
        return 0

    floor = catalog_price_floor()
    floor_label = "none" if floor is None else f"${floor:.2f}"
    key_on = bool(pokemon_tcg_api_key())
    LOG.info(
        "Katalog mode=%s · pokemontcg API key=%s · pace=%gs · min %s",
        mode,
        "yes" if key_on else "no",
        rate_limit_sleep_seconds(),
        floor_label,
    )
    if key_on:
        LOG.info(
            "Koristim postojeći POKEMONTCG_API_KEY (legacy; API deprecated, keys do 2027-03-01)."
        )
    else:
        LOG.info(
            "Bez POKEMONTCG_API_KEY — unkeyed pace (~2.5s). "
            "Novi key više nije dostupan (pokemontcg.io deprecated)."
        )

    if mode == "gapfill":
        sets, stats = select_gapfill_catalog_targets()
        LOG.info(
            "Gap-fill katalog: api_sets=%s complete=%s missing=%s incomplete=%s "
            "selected=%s budget=%s",
            stats.get("api_sets"),
            stats.get("complete"),
            stats.get("missing"),
            stats.get("incomplete"),
            stats.get("selected"),
            stats.get("budget"),
        )
        if not sets:
            LOG.info(
                "Korak 1/3: katalog kompletan (%s/%s setova) — ništa za dohvatiti.",
                stats.get("complete"),
                stats.get("api_sets"),
            )
            return 0
    else:
        sets = resolve_catalog_targets()

    labels = ", ".join(f"{name} ({sid})" for sid, name in sets[:12])
    if len(sets) > 12:
        labels = f"{labels}, … (+{len(sets) - 12} more)"
    LOG.info(
        "Korak 1/3: osvježavam katalog karata [%s setova: %s], min %s...",
        len(sets),
        labels,
        floor_label,
    )
    raw = fetch_cards(set_ids=list(sets), paginate=True)
    if not raw:
        raise RuntimeError(
            "Katalog: nijedan set nije vraćen s pokemontcg.io "
            "(svi setovi pale ili prazan odgovor)."
        )
    cleaned = clean_cards(raw, min_price=floor)
    if not cleaned:
        raise RuntimeError(
            f"Katalog: {len(raw)} sirovih karata, ali 0 nakon filtera "
            f"(min {floor_label})."
        )
    saved = save_cards(cleaned)
    LOG.info("Katalog: %s očišćenih karata, %s spremljenih/ažuriranih u Supabase.", len(cleaned), saved)
    return saved


def refresh_price_history() -> dict[str, int]:
    from config import _secret, justtcg_nightly_request_budget
    from generate_history import ensure_price_history, generate_price_history
    from justtcg_client import (
        configure_justtcg_request_budget,
        justtcg_api_key,
        justtcg_request_count,
        reset_justtcg_request_count,
    )
    from sync_justtcg import sync_justtcg_price_history
    from sync_live_data import sync_live_price_history

    LOG.info("Korak 2/3: sinkroniziram price_history...")

    raw_limit = os.environ.get("NIGHTLY_CARD_LIMIT", "").strip()
    if raw_limit.lower() in {"", "all", "none"}:
        limit: int | None = None
    else:
        limit = int(raw_limit)

    # Preferiraj JustTCG (NM + history); fallback PokéWallet; pa sintetički.
    if justtcg_api_key():
        # Always cap nightly (unless NIGHTLY_ALLOW_UNLIMITED_JUSTTCG=1).
        # Pre-budget card_limit=all runs burned 1k+ requests in a single night.
        budget = justtcg_nightly_request_budget()
        reset_justtcg_request_count()
        configure_justtcg_request_budget(budget)
        if limit is None and budget is not None:
            LOG.warning(
                "NIGHTLY_CARD_LIMIT=all with request_budget=%s — "
                "sync stops at budget, not at full catalog.",
                budget,
            )
        LOG.info(
            "JustTCG sync (NM) — card_limit=%s request_budget=%s",
            "all" if limit is None else limit,
            budget if budget is not None else "unlimited",
        )
        stats = sync_justtcg_price_history(limit=limit)
        filled = generate_price_history(replace=False)
        LOG.info(
            "JustTCG: updated=%s skipped=%s saved=%s total_history=%s "
            "synthetic_new=%s unmatched_sets=%s requests=%s",
            stats["updated"],
            stats["skipped"],
            stats["saved"],
            stats["total_history"],
            filled,
            stats.get("unmatched_sets_count", 0),
            stats.get("justtcg_requests", justtcg_request_count()),
        )
        try:
            from services.spot_qa import build_and_save_snapshot

            qa = build_and_save_snapshot(
                unmatched_sets=list(stats.get("unmatched_sets") or []),
                justtcg_stats=stats,
            )
            LOG.info(
                "Spot QA snapshot: history_coverage=%s%% fresh=%s%% sure_rows=%s unmatched=%s",
                qa.get("history_coverage_pct"),
                qa.get("fresh_history_pct"),
                qa.get("sure_rows"),
                qa.get("unmatched_sets_count"),
            )
            # Soft-heal absurd clusters + auto-quarantine Energy/rarity-cap tips.
            # Full drain + UNDER verify also runs again AFTER retrain (see main).
            try:
                from services.spot_heal import (
                    heal_auto_unsafe_spots,
                    heal_poisoned_spots,
                    nightly_spot_heal_limit,
                    nightly_spot_refetch_limit,
                )

                heal_limit = nightly_spot_heal_limit()
                if heal_limit is None or heal_limit > 0:
                    # Persist clear-cut unsafe tips off the sure desk (no human clicks).
                    auto = heal_auto_unsafe_spots(mode="null_market", limit=heal_limit)
                    LOG.info(
                        "Auto-quarantine: count=%s quotes=%s keys=%s",
                        auto.get("count"),
                        auto.get("quotes_quarantined"),
                        auto.get("poison_keys"),
                    )
                    qa["spot_auto_quarantine"] = {
                        "count": auto.get("count"),
                        "quotes_quarantined": auto.get("quotes_quarantined"),
                        "poison_keys": auto.get("poison_keys"),
                    }
                    refetch_lim = nightly_spot_refetch_limit()
                    if refetch_lim > 0 and int(qa.get("spot_quarantine_rows") or 0) > 0:
                        heal = heal_poisoned_spots(mode="refetch", limit=refetch_lim)
                        LOG.info(
                            "Spot heal: count=%s updated=%s skip_poison=%s keys=%s",
                            heal.get("count"),
                            heal.get("updated"),
                            heal.get("skip_poison"),
                            heal.get("poison_keys"),
                        )
                        qa["spot_heal"] = {
                            "count": heal.get("count"),
                            "updated": heal.get("updated"),
                            "skip_poison": heal.get("skip_poison"),
                            "poison_keys": heal.get("poison_keys"),
                        }
                    from services.spot_qa import save_spot_qa_snapshot

                    save_spot_qa_snapshot(qa)
            except Exception as heal_exc:
                LOG.warning("Spot heal failed: %s", heal_exc)
        except Exception as qa_exc:
            LOG.warning("Spot QA snapshot failed: %s", qa_exc)
        return stats

    tcg_key = _secret("TCG_API_KEY")
    if not tcg_key:
        LOG.warning(
            "JUSTTCG_API_KEY i TCG_API_KEY nisu postavljeni — "
            "koristim lokalni ensure_price_history()."
        )
        ensure_price_history()
        generate_price_history(replace=False)
        return {"updated": 0, "skipped": 0, "saved": 0, "total_history": 0}

    LOG.info("PokéWallet sync — limit: %s", "sve karte" if limit is None else f"top {limit}")
    stats = sync_live_price_history(limit=limit)
    filled = generate_price_history(replace=False)
    LOG.info(
        "Povijest: updated=%s skipped=%s saved=%s total_history=%s synthetic_new=%s",
        stats["updated"],
        stats["skipped"],
        stats["saved"],
        stats["total_history"],
        filled,
    )
    return stats


def retrain_ai() -> dict[str, float | int]:
    from datetime import date, timedelta

    from ai_xgboost import ARTIFACT_ID_30D, load_history, retrain_model
    from config import PRICE_HISTORY_DAYS
    from services.exchange import build_market_board
    from trading_signals import PORTFOLIO_HORIZON_DAYS

    LOG.info("Korak 3/3: re-trening XGBoost (7d board + %sd portfolio)...", PORTFOLIO_HORIZON_DAYS)
    # One scoped Supabase history pull for 7d + 30d + board rebuild.
    # Full-table price_history (~2M rows) times out on PostgREST (57014).
    window_days = int(PRICE_HISTORY_DAYS) + int(PORTFOLIO_HORIZON_DAYS) + 21
    since = (date.today() - timedelta(days=window_days)).isoformat()
    LOG.info(
        "Retrain history window: since=%s (%sd = PRICE_HISTORY_DAYS+%sd+21)",
        since,
        window_days,
        PORTFOLIO_HORIZON_DAYS,
    )
    history = load_history(since_date=since)
    metrics = retrain_model(history=history)
    LOG.info(
        "Model 7d: cards=%s rows=%s RMSE=%.4f R2=%.4f "
        "rmse/naive=%s dir_acc=%s%% pred_flat=%s%% conformal_q=%s "
        "wf_folds=%s wf_dir=%s%% wf_rmse/naive=%s",
        metrics["cards"],
        metrics["rows"],
        metrics["rmse"],
        metrics["r2"],
        f"{metrics['rmse_vs_naive']:.3f}" if "rmse_vs_naive" in metrics else "—",
        f"{metrics['direction_accuracy_pct']:.1f}"
        if "direction_accuracy_pct" in metrics
        else "—",
        f"{metrics['pred_flat_pct']:.1f}" if "pred_flat_pct" in metrics else "—",
        f"{metrics['conformal_q']:.4f}" if "conformal_q" in metrics else "—",
        metrics.get("wf_folds", 0),
        f"{metrics['wf_direction_accuracy_pct']:.1f}"
        if "wf_direction_accuracy_pct" in metrics
        else "—",
        f"{metrics['wf_rmse_vs_naive']:.3f}" if "wf_rmse_vs_naive" in metrics else "—",
    )
    try:
        metrics_30 = retrain_model(
            horizon_days=int(PORTFOLIO_HORIZON_DAYS),
            artifact_id=ARTIFACT_ID_30D,
            history=history,
        )
        LOG.info(
            "Model 30d: cards=%s rows=%s RMSE=%.4f R2=%.4f "
            "rmse/naive=%s dir_acc=%s%% pred_flat=%s%% conformal_q=%s",
            metrics_30["cards"],
            metrics_30["rows"],
            metrics_30["rmse"],
            metrics_30["r2"],
            f"{metrics_30['rmse_vs_naive']:.3f}" if "rmse_vs_naive" in metrics_30 else "—",
            f"{metrics_30['direction_accuracy_pct']:.1f}"
            if "direction_accuracy_pct" in metrics_30
            else "—",
            f"{metrics_30['pred_flat_pct']:.1f}" if "pred_flat_pct" in metrics_30 else "—",
            f"{metrics_30['conformal_q']:.4f}" if "conformal_q" in metrics_30 else "—",
        )
        metrics = dict(metrics)
        metrics["portfolio_30d"] = {
            k: metrics_30[k]
            for k in (
                "rows",
                "rmse",
                "r2",
                "rmse_vs_naive",
                "direction_accuracy_pct",
                "pred_flat_pct",
                "conformal_q",
                "horizon_days",
                "wf_folds",
                "wf_direction_accuracy_pct",
                "wf_rmse_vs_naive",
            )
            if k in metrics_30
        }
    except Exception as exc:
        LOG.warning("30d portfolio model retrain failed: %s", exc)
    _history, quotes, _model = build_market_board(persist=True, history=history)
    quote_n = int(len(quotes)) if quotes is not None else 0
    metrics = dict(metrics)
    metrics["quotes"] = quote_n
    LOG.info("market_quotes refreshed: %s rows", quote_n)
    if quote_n <= 0:
        raise RuntimeError("market_quotes board is empty after rebuild")
    try:
        from services.email_alerts import send_watchlist_digests

        digest = send_watchlist_digests(quotes)
        metrics["alert_emails_sent"] = int(digest.get("sent") or 0)
        LOG.info("watchlist email digests: %s", digest)
    except Exception as exc:
        LOG.warning("watchlist email digests failed: %s", exc)
    try:
        from services.discord_alerts import send_sure_discord_digest

        discord = send_sure_discord_digest(quotes)
        metrics["alert_discord_sent"] = int(discord.get("sent") or 0)
        metrics["alert_discord_n"] = int(discord.get("alerts") or 0)
        LOG.info("watchlist Discord digest: %s", discord)
    except Exception as exc:
        LOG.warning("watchlist Discord digest failed: %s", exc)
    return metrics


def run_nightly() -> int:
    """Faze su izolirane — katalog može pasti, sync/retrain i dalje idu.

    Phase C3 SLO: retrain must refresh market_quotes, and wall clock must stay
    under NIGHTLY_SLO_MAX_SECONDS (soft cap before GitHub's 180m hard kill).
    """
    from config import PROJECT_ROOT, get_supabase_credentials, nightly_slo_max_seconds
    from database import ensure_seed_database, init_db
    from main import print_summary
    from services.nightly_slo import PhaseTimer, evaluate_nightly_slo

    started = datetime.now()
    slo_max = nightly_slo_max_seconds()
    LOG.info("=== Nightly update start (%s) ===", started.isoformat(timespec="seconds"))
    LOG.info("Radni direktorij: %s", PROJECT_ROOT)
    LOG.info("GITHUB_ACTIONS=%s", os.environ.get("GITHUB_ACTIONS", ""))
    LOG.info("Nightly SLO max wall clock: %ss (%.0fm)", slo_max, slo_max / 60.0)

    url, key = get_supabase_credentials()
    LOG.info("Supabase URL host: %s", url)
    LOG.info("Supabase key: len=%s prefix=%s", len(key), (key[:8] + "…") if key else "(empty)")

    try:
        init_db()
        if ensure_seed_database():
            LOG.info("Seed uvezen u prazan Supabase.")
    except Exception as exc:
        _report_error("init_db", exc)
        return 1

    failures: list[str] = []
    phase_times: dict[str, float] = {}
    quotes_written = 0

    def _run_phase(name: str, fn) -> None:
        timer = PhaseTimer(name)
        try:
            result = fn()
            elapsed = timer.finish(ok=True)
            phase_times[name] = round(elapsed, 1)
            LOG.info("Phase %s ok in %.1fs", name, elapsed)
            return result
        except Exception as exc:
            elapsed = timer.finish(ok=False, error=str(exc))
            phase_times[name] = round(elapsed, 1)
            _report_error(name, exc)
            failures.append(name)
            LOG.warning("Phase %s failed after %.1fs", name, elapsed)
            return None

    _run_phase("catalog", refresh_card_catalog)
    if "catalog" in failures:
        LOG.warning("Nastavljam s postojećim kartama u bazi.")

    _run_phase("history", refresh_price_history)

    # Optional: resolve missing cards.tcgplayer_id (rate-limited JustTCG searches).
    if _env_flag("NIGHTLY_BACKFILL_TCP"):
        def _tcp_backfill():
            from backfill_tcgplayer_ids import backfill_tcgplayer_ids

            limit_raw = os.environ.get("NIGHTLY_BACKFILL_TCP_LIMIT", "300").strip()
            limit = int(limit_raw) if limit_raw.isdigit() else 300
            stats = backfill_tcgplayer_ids(
                limit=limit,
                only_missing=True,
                resume=True,
                allow_justtcg=_env_flag("NIGHTLY_BACKFILL_JUSTTCG"),
            )
            LOG.info(
                "tcgplayer_id backfill scanned=%s updated=%s skipped=%s failed=%s "
                "tcgplayer=%s justtcg=%s rate_limited=%s stopped_early=%s",
                stats["scanned"],
                stats["updated"],
                stats["skipped"],
                stats["failed"],
                stats.get("from_tcgplayer", 0),
                stats.get("from_justtcg", 0),
                stats.get("rate_limited", 0),
                stats.get("stopped_early", 0),
            )
            return stats

        _run_phase("tcp_backfill", _tcp_backfill)

    def _ebay():
        from services.ebay_liquidity import harvest_ebay_liquidity

        ebay_liq = harvest_ebay_liquidity()
        LOG.info("eBay liquidity harvest: %s", ebay_liq)
        return ebay_liq

    _run_phase("ebay_liquidity", _ebay)

    def _retrain():
        nonlocal quotes_written
        metrics = retrain_ai()
        quotes_written = int((metrics or {}).get("quotes") or 0)
        return metrics

    _run_phase("retrain", _retrain)

    try:
        from auth import purge_expired_auth_sessions

        purged = purge_expired_auth_sessions()
        LOG.info("auth_sessions purge: %s", purged)
    except Exception as exc:
        _report_error("purge_auth_sessions", exc)
        # Non-fatal — session table bloat should not fail the nightly.

    try:
        print_summary()
    except Exception as exc:
        _report_error("print_summary", exc)

    # Bust API board TTL so cold Radar does not keep pre-retrain quotes (M0.5).
    try:
        from api.catalog_service import clear_board_cache

        clear_board_cache()
        LOG.info("Board cache cleared after nightly retrain/quotes")
    except Exception as cache_exc:
        LOG.warning("Board cache clear failed: %s", cache_exc)

    # Post-retrain desk sweep: retrain rewrites market_quotes and would otherwise
    # put Energy / cluster / wild-7d tips back on the sure desk until a human
    # clicks Heal 10-at-a-time. Drain automatically, then verify top UNDERs.
    try:
        from services.spot_heal import sweep_desk_poison, verify_top_under_spots

        sweep = sweep_desk_poison()
        LOG.info(
            "Post-retrain desk sweep: auto=%s poison=%s quotes=%s keys=%s",
            sweep.get("auto_quarantined"),
            sweep.get("poison_nulled"),
            sweep.get("quotes_quarantined"),
            sweep.get("poison_keys"),
        )
        verify = verify_top_under_spots()
        LOG.info(
            "Post-retrain UNDER verify: count=%s updated=%s skip_poison=%s under_total=%s",
            verify.get("count"),
            verify.get("updated"),
            verify.get("skip_poison"),
            verify.get("under_total"),
        )
        try:
            from api.catalog_service import clear_board_cache

            clear_board_cache()
        except Exception:
            pass
        try:
            from services.spot_qa import load_spot_qa_snapshot, save_spot_qa_snapshot

            snap = load_spot_qa_snapshot() or {}
            snap["post_retrain_desk_sweep"] = {
                "auto_quarantined": sweep.get("auto_quarantined"),
                "poison_nulled": sweep.get("poison_nulled"),
                "quotes_quarantined": sweep.get("quotes_quarantined"),
            }
            snap["post_retrain_under_verify"] = {
                "count": verify.get("count"),
                "updated": verify.get("updated"),
                "skip_poison": verify.get("skip_poison"),
                "under_total": verify.get("under_total"),
            }
            save_spot_qa_snapshot(snap)
        except Exception as snap_exc:
            LOG.warning("Post-retrain sweep snapshot failed: %s", snap_exc)
    except Exception as sweep_exc:
        LOG.warning("Post-retrain desk sweep failed: %s", sweep_exc)

    sure_rows_live: int | None = None
    try:
        from services.spot_qa import compute_live_spot_qa

        qa_live = compute_live_spot_qa()
        sure_rows_live = int(qa_live.get("sure_rows") or 0)
    except Exception as sure_exc:
        LOG.warning("Post-nightly sure_rows sample failed: %s", sure_exc)

    elapsed = (datetime.now() - started).total_seconds()
    slo = evaluate_nightly_slo(
        elapsed_s=elapsed,
        max_seconds=slo_max,
        quotes_written=quotes_written,
        failures=failures,
        sure_rows=sure_rows_live,
    )
    LOG.info(
        "Nightly SLO: ok=%s elapsed=%.1fs max=%ss quotes_written=%s sure_rows=%s reasons=%s phases=%s",
        slo["slo_ok"],
        slo["elapsed_s"],
        slo["max_seconds"],
        slo["quotes_written"],
        slo.get("sure_rows"),
        slo["slo_reasons"],
        phase_times,
    )
    try:
        from services.spot_qa import load_spot_qa_snapshot, save_spot_qa_snapshot

        snap = load_spot_qa_snapshot() or {}
        snap.update(
            {
                "sure_rows": (
                    sure_rows_live
                    if sure_rows_live is not None
                    else snap.get("sure_rows")
                ),
                "quotes_total": max(int(snap.get("quotes_total") or 0), quotes_written),
                "nightly_slo_ok": bool(slo["slo_ok"]),
                "nightly_elapsed_s": float(slo["elapsed_s"]),
                "nightly_slo_max_s": int(slo["max_seconds"]),
                "quotes_written": int(slo["quotes_written"]),
                "nightly_slo_reasons": list(slo["slo_reasons"]),
                "nightly_phase_times": dict(phase_times),
            }
        )
        save_spot_qa_snapshot(snap)
    except Exception as qa_exc:
        LOG.warning("Nightly SLO snapshot update failed: %s", qa_exc)

    if not slo["slo_ok"]:
        for reason in slo["slo_reasons"]:
            if reason not in failures:
                failures.append(reason)

    if failures:
        print(
            f"Nightly update FAILED after {elapsed:.1f}s — failed phases: {', '.join(failures)}",
            file=sys.__stderr__,
        )
        print(
            f"::error title=Nightly update::Failed phases: {', '.join(failures)}",
            file=sys.__stderr__,
        )
        LOG.error("Nightly gotov s greškama (%s) za %.1f s", failures, elapsed)
        return 1

    LOG.info("=== Nightly update gotov za %.1f s (SLO ok) ===", elapsed)
    return 0


def nightly_runner_allowed() -> tuple[bool, str]:
    """Nightly is GitHub Actions–only unless explicitly overridden.

    Returns (allowed, reason). Local/cron hosts must set ``NIGHTLY_ALLOW_LOCAL=1``
    for a one-off debug run — do not use that for production scheduling.
    """
    if str(os.environ.get("GITHUB_ACTIONS") or "").strip().lower() in {"1", "true", "yes"}:
        return True, "github_actions"
    if str(os.environ.get("NIGHTLY_ALLOW_LOCAL") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return True, "local_override"
    return False, "blocked"


def main() -> int:
    allowed, reason = nightly_runner_allowed()
    if not allowed:
        msg = (
            "Nightly update runs only via GitHub Actions "
            "(.github/workflows/nightly_update.yml). "
            "For a one-off local debug, set NIGHTLY_ALLOW_LOCAL=1."
        )
        print(msg, file=sys.__stderr__)
        print(f"::error title=Nightly blocked::{msg}", file=sys.__stderr__)
        return 2
    try:
        from config import AUTOMATION_LOG

        setup_logging(AUTOMATION_LOG)
        LOG.info("Nightly runner allowed (%s)", reason)
        return run_nightly()
    except Exception as e:
        print(f"Nightly bootstrap FAILED: {type(e).__name__}: {e}", file=sys.__stderr__)
        traceback.print_exc(file=sys.__stderr__)
        print(f"::error title=Nightly bootstrap::{type(e).__name__}: {e}", file=sys.__stderr__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
