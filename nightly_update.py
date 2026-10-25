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
    # Na GitHub Actionsu ne diraj stderr — traceback mora ići čisto u log.
    if not os.environ.get("GITHUB_ACTIONS"):
        sys.stderr = _TeeStream(sys.__stderr__, LOG, logging.ERROR)


def refresh_card_catalog() -> int:
    from api_client import clean_cards, fetch_cards
    from config import CATALOG_SERIES
    from main import save_cards

    LOG.info("Korak 1/3: osvježavam katalog karata (%s)...", ", ".join(CATALOG_SERIES))
    raw = fetch_cards(series_names=CATALOG_SERIES, paginate=True)
    cleaned = clean_cards(raw)
    saved = save_cards(cleaned)
    LOG.info("Katalog: %s očišćenih karata, %s spremljenih/ažuriranih u Supabase.", len(cleaned), saved)
    return saved


def refresh_price_history() -> dict[str, int]:
    from config import _secret
    from generate_history import ensure_price_history
    from sync_live_data import sync_live_price_history

    LOG.info("Korak 2/3: sinkroniziram price_history...")
    tcg_key = _secret("TCG_API_KEY")
    if not tcg_key:
        LOG.warning("TCG_API_KEY nije postavljen — koristim lokalni ensure_price_history().")
        ensure_price_history()
        return {"updated": 0, "skipped": 0, "saved": 0, "total_history": 0}

    # NIGHTLY_CARD_LIMIT=100 za brži test; prazno/None = sve karte.
    raw_limit = os.environ.get("NIGHTLY_CARD_LIMIT", "").strip()
    limit: int | None
    if raw_limit.lower() in {"", "all", "none"}:
        limit = None
    else:
        limit = int(raw_limit)
    LOG.info("Sync limit: %s", "sve karte" if limit is None else f"top {limit}")
    stats = sync_live_price_history(limit=limit)
    LOG.info(
        "Povijest: updated=%s skipped=%s saved=%s total_history=%s",
        stats["updated"],
        stats["skipped"],
        stats["saved"],
        stats["total_history"],
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
    """Glavna noćna logika — sve greške idu u terminal (GitHub Actions log)."""
    from config import PROJECT_ROOT
    from database import init_db
    from main import print_summary

    started = datetime.now()
    try:
        LOG.info("=== Nightly update start (%s) ===", started.isoformat(timespec="seconds"))
        LOG.info("Radni direktorij: %s", PROJECT_ROOT)
        LOG.info("GITHUB_ACTIONS=%s", os.environ.get("GITHUB_ACTIONS", ""))

        init_db()
        refresh_card_catalog()
        refresh_price_history()
        retrain_ai()
        print_summary()

        elapsed = (datetime.now() - started).total_seconds()
        LOG.info("=== Nightly update gotov za %.1f s ===", elapsed)
        return 0
    except Exception as e:
        print(f"Nightly update FAILED: {type(e).__name__}: {e}", file=sys.__stderr__)
        traceback.print_exc(file=sys.__stderr__)
        try:
            LOG.exception("Nightly update nije uspio: %s", e)
        except Exception:
            pass
        return 1


def main() -> int:
    try:
        from config import AUTOMATION_LOG

        setup_logging(AUTOMATION_LOG)
        return run_nightly()
    except Exception as e:
        print(f"Nightly bootstrap FAILED: {type(e).__name__}: {e}", file=sys.__stderr__)
        traceback.print_exc(file=sys.__stderr__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
