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


def refresh_card_catalog() -> int:
    from api_client import clean_cards, fetch_cards
    from config import CATALOG_MIN_PRICE, CATALOG_SETS
    from main import save_cards

    labels = ", ".join(f"{name} ({sid})" for sid, name in CATALOG_SETS)
    LOG.info(
        "Korak 1/3: osvježavam katalog karata [%s], min $%.2f...",
        labels,
        CATALOG_MIN_PRICE,
    )
    raw = fetch_cards(set_ids=list(CATALOG_SETS), paginate=True)
    if not raw:
        raise RuntimeError(
            "Katalog: nijedan set nije vraćen s pokemontcg.io "
            "(svi setovi pale ili prazan odgovor)."
        )
    cleaned = clean_cards(raw, min_price=CATALOG_MIN_PRICE)
    if not cleaned:
        raise RuntimeError(
            f"Katalog: {len(raw)} sirovih karata, ali 0 nakon filtera "
            f"min ${CATALOG_MIN_PRICE:.2f}."
        )
    saved = save_cards(cleaned)
    LOG.info("Katalog: %s očišćenih karata, %s spremljenih/ažuriranih u Supabase.", len(cleaned), saved)
    return saved


def refresh_price_history() -> dict[str, int]:
    from config import _secret
    from generate_history import ensure_price_history, generate_price_history
    from justtcg_client import justtcg_api_key
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
        LOG.info(
            "JustTCG sync (NM) — limit: %s",
            "svi curated setovi" if limit is None else f"top {limit}",
        )
        stats = sync_justtcg_price_history(limit=limit)
        filled = generate_price_history(replace=False)
        LOG.info(
            "JustTCG: updated=%s skipped=%s saved=%s total_history=%s synthetic_new=%s",
            stats["updated"],
            stats["skipped"],
            stats["saved"],
            stats["total_history"],
            filled,
        )
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
    from ai_xgboost import retrain_model

    LOG.info("Korak 3/3: re-trening XGBoost na proširenom nizu...")
    metrics = retrain_model()
    LOG.info(
        "Model: cards=%s rows=%s RMSE=%.4f R2=%.4f",
        metrics["cards"],
        metrics["rows"],
        metrics["rmse"],
        metrics["r2"],
    )
    return metrics


def run_nightly() -> int:
    """Faze su izolirane — katalog može pasti, sync/retrain i dalje idu."""
    from config import PROJECT_ROOT, get_supabase_credentials
    from database import ensure_seed_database, init_db
    from main import print_summary

    started = datetime.now()
    LOG.info("=== Nightly update start (%s) ===", started.isoformat(timespec="seconds"))
    LOG.info("Radni direktorij: %s", PROJECT_ROOT)
    LOG.info("GITHUB_ACTIONS=%s", os.environ.get("GITHUB_ACTIONS", ""))

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

    if _env_flag("NIGHTLY_SKIP_CATALOG"):
        LOG.info("Korak 1/3: PRESKOČEN (NIGHTLY_SKIP_CATALOG=1).")
    else:
        try:
            refresh_card_catalog()
        except Exception as exc:
            _report_error("refresh_card_catalog", exc)
            failures.append("catalog")
            LOG.warning("Nastavljam s postojećim kartama u bazi.")

    try:
        refresh_price_history()
    except Exception as exc:
        _report_error("refresh_price_history", exc)
        failures.append("history")

    # Optional: resolve missing cards.tcgplayer_id (rate-limited JustTCG searches).
    if _env_flag("NIGHTLY_BACKFILL_TCP"):
        try:
            from backfill_tcgplayer_ids import backfill_tcgplayer_ids

            limit_raw = os.environ.get("NIGHTLY_BACKFILL_TCP_LIMIT", "10").strip()
            limit = int(limit_raw) if limit_raw.isdigit() else 10
            stats = backfill_tcgplayer_ids(limit=limit, only_missing=True)
            LOG.info(
                "tcgplayer_id backfill scanned=%s updated=%s skipped=%s failed=%s "
                "rate_limited=%s stopped_early=%s",
                stats["scanned"],
                stats["updated"],
                stats["skipped"],
                stats["failed"],
                stats.get("rate_limited", 0),
                stats.get("stopped_early", 0),
            )
        except Exception as exc:
            _report_error("backfill_tcgplayer_ids", exc)
            failures.append("tcp_backfill")

    try:
        retrain_ai()
    except Exception as exc:
        _report_error("retrain_ai", exc)
        failures.append("retrain")

    try:
        print_summary()
    except Exception as exc:
        _report_error("print_summary", exc)

    elapsed = (datetime.now() - started).total_seconds()
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

    LOG.info("=== Nightly update gotov za %.1f s ===", elapsed)
    return 0


def main() -> int:
    try:
        from config import AUTOMATION_LOG

        setup_logging(AUTOMATION_LOG)
        return run_nightly()
    except Exception as e:
        print(f"Nightly bootstrap FAILED: {type(e).__name__}: {e}", file=sys.__stderr__)
        traceback.print_exc(file=sys.__stderr__)
        print(f"::error title=Nightly bootstrap::{type(e).__name__}: {e}", file=sys.__stderr__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
