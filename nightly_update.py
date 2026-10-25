# pip install requests python-dotenv sqlalchemy pandas xgboost scikit-learn
"""Noćni radnik: katalog → PokéWallet snimke → re-trening XGBoost."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import requests

from ai_xgboost import retrain_model
from api_client import clean_cards, fetch_cards
from config import AUTOMATION_LOG, CATALOG_SERIES, PROJECT_ROOT, TCG_API_KEY
from database import init_db
from generate_history import ensure_price_history
from main import print_summary, save_cards
from sync_live_data import sync_live_price_history

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


def setup_logging(log_path: Path = AUTOMATION_LOG) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    LOG.handlers.clear()
    LOG.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOG.addHandler(file_handler)

    # Konzola bez dvostrukog zapisa kad Tee već piše u LOG.
    console = logging.StreamHandler(sys.__stdout__)
    console.setFormatter(formatter)
    LOG.addHandler(console)

    sys.stdout = _TeeStream(sys.__stdout__, LOG, logging.INFO)
    sys.stderr = _TeeStream(sys.__stderr__, LOG, logging.ERROR)


def refresh_card_catalog() -> int:
    """Povlači tisuće karata iz Scarlet & Violet + Sword & Shield era."""
    LOG.info("Korak 1/3: osvježavam katalog karata (%s)...", ", ".join(CATALOG_SERIES))
    raw = fetch_cards(series_names=CATALOG_SERIES, paginate=True)
    cleaned = clean_cards(raw)
    saved = save_cards(cleaned)
    LOG.info("Katalog: %s očišćenih karata, %s spremljenih/ažuriranih u Supabase.", len(cleaned), saved)
    return saved


def refresh_price_history() -> dict[str, int]:
    """Za sve karte u bazi dohvaća snimke s PokéWalleta (ili lokalni fallback)."""
    LOG.info("Korak 2/3: sinkroniziram price_history za SVE karte...")
    if not TCG_API_KEY:
        LOG.warning("TCG_API_KEY nije postavljen — koristim lokalni ensure_price_history().")
        ensure_price_history()
        return {"updated": 0, "skipped": 0, "saved": 0, "total_history": 0}

    stats = sync_live_price_history(limit=None)
    LOG.info(
        "Povijest: updated=%s skipped=%s saved=%s total_history=%s",
        stats["updated"],
        stats["skipped"],
        stats["saved"],
        stats["total_history"],
    )
    return stats


def retrain_ai() -> dict[str, float | int]:
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
    started = datetime.now()
    LOG.info("=== Nightly update start (%s) ===", started.isoformat(timespec="seconds"))
    LOG.info("Radni direktorij: %s", PROJECT_ROOT)

    try:
        init_db()
        refresh_card_catalog()
        refresh_price_history()
        retrain_ai()
        print_summary()
    except Exception as exc:
        LOG.exception("Nightly update nije uspio: %s", exc)
        return 1

    elapsed = (datetime.now() - started).total_seconds()
    LOG.info("=== Nightly update gotov za %.1f s ===", elapsed)
    return 0


def main() -> int:
    setup_logging()
    # Pokemontcg/PokéWallet printovi idu u stdout; StreamHandler ih i dalje vidi.
    # Ključne faze i greške idu u automation.log.
    try:
        return run_nightly()
    except requests.RequestException as exc:
        LOG.error("Mrežna greška: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
