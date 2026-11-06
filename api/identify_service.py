"""Match OCR / free-text from a card photo to Soft Ink catalog rows.

OCR itself runs in the browser (tesseract.js). This service only ranks board hits
so the camera path lands on the same fair/edge desk as Browse.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from api.catalog_service import load_board, row_to_card

# Common Pokémon TCG chrome that OCR picks up but is not a card name.
_JUNK_LINE = re.compile(
    r"^(?:basic|stage\s*[12]|trainer|item|supporter|stadium|pok[eé]mon|"
    r"weakness|resistance|retreat|illustrator|rule\s*box|ability|"
    r"attacks?|damage|hp|evolves?\s+from|put\s+this|when\s+you|"
    r"during|once\s+during|this\s+attack|energy|colorless|"
    r"copyright|nintendo|creatures|game\s*freak|the\s+pok[eé]mon|"
    r"ultra\s*rare|illustration\s*rare|special\s*illustration|"
    r"double\s*rare|ace\s*spec|hyper\s*rare|secret\s*rare)$",
    re.I,
)

_COLLECTOR = re.compile(
    r"\b([A-Z]{0,3}\d{1,3})\s*/\s*([A-Z]{0,3}\d{1,3})\b",
    re.I,
)
_CARD_ID = re.compile(r"\b([a-z]{1,6}\d{0,2})-(\d{1,3}[a-z]?)\b", re.I)
_SOLO_NUM = re.compile(r"\b(?:no\.?\s*)?(\d{1,3})\b", re.I)


def normalize_number_token(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if "/" in text:
        text = text.split("/", 1)[0].strip()
    text = re.sub(r"^0+", "", text) or "0"
    return text


def parse_ocr_clues(raw: str) -> dict[str, Any]:
    """Pull name / number / set-ish hints from messy OCR text."""
    text = str(raw or "").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]

    collector_left: str | None = None
    collector_full: str | None = None
    for ln in lines:
        m = _COLLECTOR.search(ln)
        if m:
            collector_left = normalize_number_token(m.group(1))
            collector_full = f"{m.group(1)}/{m.group(2)}".lower()
            break

    card_ids: list[str] = []
    for m in _CARD_ID.finditer(text):
        card_ids.append(f"{m.group(1).lower()}-{normalize_number_token(m.group(2))}")

    name_candidates: list[tuple[int, str]] = []
    for idx, ln in enumerate(lines):
        clean = re.sub(r"[^A-Za-z0-9' .\-]", "", ln).strip()
        if len(clean) < 3:
            continue
        if _JUNK_LINE.match(clean):
            continue
        if _COLLECTOR.search(clean) and len(clean) < 12:
            continue
        letters = sum(ch.isalpha() for ch in clean)
        if letters < 3:
            continue
        # Prefer title-ish lines (not full attack paragraphs).
        if len(clean.split()) > 8:
            continue
        name_candidates.append((idx, clean))

    # Prefer early lines — card title sits near the top — then longer text.
    name_candidates.sort(key=lambda t: (min(t[0], 8), -len(t[1])))
    name_hints = [s for _, s in name_candidates[:6]]

    return {
        "text": text.strip(),
        "name_hints": name_hints,
        "number": collector_left,
        "collector": collector_full,
        "card_ids": card_ids[:4],
    }


def _name_score(card_name: str, hints: list[str]) -> float:
    target = re.sub(r"[^a-z0-9 ]", "", str(card_name or "").lower()).strip()
    if not target or not hints:
        return 0.0
    best = 0.0
    for hint in hints:
        h = re.sub(r"[^a-z0-9 ]", "", hint.lower()).strip()
        if not h:
            continue
        if target == h or target in h or h in target:
            best = max(best, 1.0)
            continue
        ratio = SequenceMatcher(None, target, h).ratio()
        # Token overlap for partial OCR ("Charizrd" / "Charizard ex")
        t_tok = set(target.split())
        h_tok = set(h.split())
        if t_tok and h_tok:
            overlap = len(t_tok & h_tok) / max(len(t_tok), len(h_tok))
            ratio = max(ratio, overlap)
        best = max(best, ratio)
    return best


def _number_from_id(card_id: str) -> str:
    if "-" not in card_id:
        return ""
    return normalize_number_token(card_id.rsplit("-", 1)[-1])


def score_card(row: dict[str, Any], clues: dict[str, Any]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    card_id = str(row.get("id") or "")
    name = str(row.get("name") or "")
    set_name = str(row.get("set_name") or "")

    for cid in clues.get("card_ids") or []:
        if cid and cid == card_id.lower():
            score += 80.0
            reasons.append("id")
            break
        if cid and card_id.lower().startswith(cid.split("-")[0]) and cid.split("-")[-1] == _number_from_id(
            card_id
        ):
            score += 55.0
            reasons.append("id-prefix")
            break

    wanted_num = clues.get("number")
    if wanted_num:
        got = _number_from_id(card_id)
        if got and got == wanted_num:
            score += 45.0
            reasons.append("number")

    hints = list(clues.get("name_hints") or [])
    name_s = _name_score(name, hints)
    # 0.72 avoids near-misses like Pikachu → Pachirisu (~0.63).
    if name_s >= 0.72:
        score += 40.0 * name_s
        reasons.append("name")
    elif hints and name_s < 0.45 and "number" in reasons:
        # OCR clearly saw a title that isn't this card — don't trust number alone.
        score = min(score, 16.0)
        reasons.append("name-mismatch")

    blob = str(clues.get("text") or "").lower()
    if set_name and len(set_name) >= 4 and set_name.lower() in blob:
        score += 12.0
        reasons.append("set")

    return score, reasons


def identify_from_text(raw: str, *, limit: int = 8) -> dict[str, Any]:
    clues = parse_ocr_clues(raw)
    board, source = load_board()
    limit = max(1, min(int(limit or 8), 24))

    if board is None or board.empty:
        return {
            "clues": clues,
            "matches": [],
            "source": source,
            "total": 0,
        }

    scored: list[tuple[float, list[str], dict[str, Any]]] = []
    for _, row in board.iterrows():
        payload = row_to_card(row)
        score, reasons = score_card(payload, clues)
        if score < 18.0:
            continue
        scored.append((score, reasons, payload))

    # If nothing crossed the bar, fall back to best name-ish catalog contains.
    if not scored and clues.get("name_hints"):
        needle = str(clues["name_hints"][0]).lower()
        mask = board["name"].astype(str).str.lower().str.contains(
            re.escape(needle[:24]),
            na=False,
            regex=True,
        )
        subset = board[mask].head(limit)
        for _, row in subset.iterrows():
            payload = row_to_card(row)
            scored.append((15.0, ["fallback"], payload))

    scored.sort(key=lambda t: t[0], reverse=True)
    matches = []
    for score, reasons, payload in scored[:limit]:
        matches.append(
            {
                "score": round(float(score), 2),
                "reasons": reasons,
                "card": payload,
            }
        )

    return {
        "clues": clues,
        "matches": matches,
        "source": source,
        "total": len(matches),
    }
