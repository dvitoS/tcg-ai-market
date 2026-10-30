"""Live JustTCG / eBay price loaders (session-cached)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import streamlit as st

from services.prices import record_justtcg_event

def resolve_tcgplayer_id(card_id: str) -> str | None:
    """DB → pokemontcg.io → JustTCG search; spremi u cards ako kolona postoji."""
    import database as db_mod
    from justtcg_client import extract_tcgplayer_product_id

    get_card = db_mod.get_card
    # Streamlit ponekad drži stari database modul — getattr izbjegava ImportError.
    update_tcp = getattr(db_mod, "update_card_tcgplayer_id", None)

    db_card = get_card(str(card_id))
    if db_card is not None and db_card.tcgplayer_id:
        return str(db_card.tcgplayer_id)

    product_id: str | None = None
    try:
        import requests

        from config import POKEMON_TCG_API_URL, TCG_API_KEY

        headers = {"Accept": "application/json"}
        if TCG_API_KEY:
            headers["X-Api-Key"] = str(TCG_API_KEY)
        response = requests.get(
            f"{POKEMON_TCG_API_URL.rstrip('/')}/{card_id}",
            headers=headers,
            timeout=25,
        )
        if response.status_code == 200:
            payload = response.json() if response.content else {}
            product_id = extract_tcgplayer_product_id(payload.get("data") or {})
    except Exception:
        product_id = None

    # Fallback: JustTCG name/number/set search (works even without pokemontcg.io).
    if not product_id and db_card is not None:
        try:
            jtcg = _justtcg_module()
            number = None
            if "-" in str(card_id):
                number = jtcg.normalize_card_number(str(card_id).rsplit("-", 1)[-1])
            hit = jtcg.search_pokemon_card(
                name=str(db_card.name or ""),
                number=number,
                set_name=str(db_card.set_name or "") or None,
            )
            if hit:
                product_id = str(hit.get("tcgplayerId") or "").strip() or None
        except Exception:
            product_id = None

    if product_id and callable(update_tcp):
        try:
            update_tcp(str(card_id), product_id)
        except Exception:
            pass
    return product_id



def _justtcg_module():
    """Učitaj justtcg_client; Streamlit drži stale sys.modules — reload po mtime."""
    from pathlib import Path

    import justtcg_client as jtcg

    path = Path(jtcg.__file__).resolve()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    prev = st.session_state.get("_justtcg_client_mtime")
    missing_api = not hasattr(jtcg, "nm_history_for_card") or not hasattr(
        jtcg, "search_pokemon_card"
    )
    if missing_api or prev != mtime:
        jtcg = importlib.reload(jtcg)
        st.session_state["_justtcg_client_mtime"] = mtime
        # Drop stale JustTCG chart caches so ranked search can refill.
        for key in list(st.session_state.keys()):
            if str(key).startswith(("justtcg_series::", "psa10_series::")):
                del st.session_state[key]
    return jtcg



def _ebay_module():
    import ebay_client as ebay

    return ebay



def load_ebay_listings(
    *,
    card_id: str,
    name: str,
    set_name: str,
) -> tuple[list[dict], str | None]:
    """Live eBay Browse listings. Cacheira uspješan rezultat u session."""
    ebay = _ebay_module()
    if not ebay.ebay_configured():
        return [], None

    number = ""
    if "-" in str(card_id):
        number = str(card_id).rsplit("-", 1)[-1].lstrip("0") or str(card_id).rsplit("-", 1)[-1]

    cache_key = f"ebay_listings::{card_id}"
    cached = st.session_state.get(cache_key)
    # Samo non-empty cache — prazan rezultat ne smije zauvijek sakriti oglase.
    if isinstance(cached, list) and cached:
        return cached, None

    try:
        rows = ebay.listings_for_card(
            name=name,
            set_name=set_name or None,
            number=number or None,
            limit=8,
        )
    except Exception as exc:
        return [], str(exc)

    if rows:
        st.session_state[cache_key] = rows
    return rows, None



def load_justtcg_series(
    *,
    tcgplayer_id: str | None,
    card_id: str,
    name: str,
    set_name: str,
) -> tuple[pd.DataFrame, str | None]:
    """Live JustTCG NM history. Cacheira samo uspješan non-empty rezultat (session)."""
    jtcg = _justtcg_module()
    if not jtcg.justtcg_api_key():
        return pd.DataFrame(columns=["date", "price"]), tcgplayer_id

    number = ""
    if "-" in str(card_id):
        number = jtcg.normalize_card_number(str(card_id).rsplit("-", 1)[-1])

    cache_key = f"justtcg_series::{card_id}::{tcgplayer_id or ''}::{number}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, pd.DataFrame) and not cached.empty:
        record_justtcg_event("cache_hit")
        return cached.copy(), tcgplayer_id

    nm_history_for_card = getattr(jtcg, "nm_history_for_card", None)
    if not callable(nm_history_for_card):
        jtcg = importlib.reload(jtcg)
        nm_history_for_card = getattr(jtcg, "nm_history_for_card", None)
    if not callable(nm_history_for_card):
        record_justtcg_event("error")
        return pd.DataFrame(columns=["date", "price"]), tcgplayer_id

    try:
        points, resolved = nm_history_for_card(
            tcgplayer_id=tcgplayer_id,
            name=name,
            number=number or None,
            set_name=set_name or None,
        )
    except Exception:
        record_justtcg_event("error")
        raise

    if not points:
        record_justtcg_event("empty")
        return pd.DataFrame(columns=["date", "price"]), resolved or tcgplayer_id

    frame = pd.DataFrame(points)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price"] = frame["price"].astype(float)
    frame = frame.sort_values("date").reset_index(drop=True)
    st.session_state[cache_key] = frame.copy()
    record_justtcg_event("live")
    if resolved and resolved != tcgplayer_id:
        try:
            import database as db_mod

            update_tcp = getattr(db_mod, "update_card_tcgplayer_id", None)
            if callable(update_tcp):
                update_tcp(str(card_id), str(resolved))
        except Exception:
            pass
    return frame, resolved or tcgplayer_id



def load_psa10_series(
    *,
    tcgplayer_id: str | None,
    card_id: str,
    name: str,
    set_name: str,
) -> tuple[pd.DataFrame, str | None, dict]:
    """Live JustTCG v2 PSA 10. Cacheira non-empty rezultat + stats."""
    jtcg = _justtcg_module()
    empty = pd.DataFrame(columns=["date", "price"])
    if not jtcg.justtcg_api_key():
        return empty, tcgplayer_id, {}

    number = ""
    if "-" in str(card_id):
        number = jtcg.normalize_card_number(str(card_id).rsplit("-", 1)[-1])

    cache_key = f"psa10_series::{card_id}::{tcgplayer_id or ''}::{number}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("frame"), pd.DataFrame):
        frame = cached["frame"]
        if not frame.empty:
            return frame.copy(), cached.get("resolved") or tcgplayer_id, dict(cached.get("stats") or {})

    psa10_history_for_card = getattr(jtcg, "psa10_history_for_card", None)
    if not callable(psa10_history_for_card):
        jtcg = importlib.reload(jtcg)
        psa10_history_for_card = getattr(jtcg, "psa10_history_for_card", None)
    if not callable(psa10_history_for_card):
        return empty, tcgplayer_id, {}

    points, resolved, stats = psa10_history_for_card(
        tcgplayer_id=tcgplayer_id,
        name=name,
        number=number or None,
        set_name=set_name or None,
    )
    if not points:
        return empty, resolved or tcgplayer_id, stats or {}

    frame = pd.DataFrame(points)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price"] = frame["price"].astype(float)
    frame = frame.sort_values("date").reset_index(drop=True)
    st.session_state[cache_key] = {
        "frame": frame.copy(),
        "resolved": resolved or tcgplayer_id,
        "stats": dict(stats or {}),
    }
    return frame, resolved or tcgplayer_id, stats or {}


