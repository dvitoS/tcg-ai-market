"use client";

import Image from "next/image";
import {
  KeyboardEvent,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { useLocale } from "@/components/LocaleProvider";
import { fetchCatalog, formatMoney } from "@/lib/api";
import { pushRecentSearch, readRecentSearches } from "@/lib/searchRecent";
import type { CatalogCard } from "@/lib/types";

export type LocalSuggestItem = {
  id: string;
  label: string;
  meta?: string;
};

type Props = {
  value: string;
  onChange: (value: string) => void;
  /** Called when user submits the query (Enter / pick recent / form). */
  onCommit: (query: string) => void;
  /** Optional: pick a catalog/local card (Trade uses this). */
  onPickCard?: (card: CatalogCard) => void;
  onPickLocal?: (item: LocalSuggestItem) => void;
  placeholder: string;
  ariaLabel: string;
  recentScope: string;
  /** catalog = live board search; local = filter provided items */
  mode?: "catalog" | "local";
  localItems?: LocalSuggestItem[];
  inputId?: string;
  autoFocus?: boolean;
};

type Hit =
  | { kind: "recent"; text: string }
  | { kind: "catalog"; card: CatalogCard }
  | { kind: "local"; item: LocalSuggestItem };

type PanelBox = { top: number; left: number; width: number };

export function SearchSuggest({
  value,
  onChange,
  onCommit,
  onPickCard,
  onPickLocal,
  placeholder,
  ariaLabel,
  recentScope,
  mode = "catalog",
  localItems = [],
  inputId,
  autoFocus,
}: Props) {
  const { t } = useLocale();
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [box, setBox] = useState<PanelBox | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [catalogHits, setCatalogHits] = useState<CatalogCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    setRecent(readRecentSearches(recentScope));
  }, [recentScope]);

  useEffect(() => {
    if (!open) return;
    const q = value.trim();
    if (mode === "local") {
      setCatalogHits([]);
      setLoading(false);
      return;
    }
    if (q.length < 2) {
      setCatalogHits([]);
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    const handle = window.setTimeout(() => {
      void fetchCatalog({ q, limit: 8, mode: "browse" })
        .then((res) => {
          if (!alive) return;
          setCatalogHits(res.items || []);
        })
        .catch(() => {
          if (!alive) return;
          setCatalogHits([]);
        })
        .finally(() => {
          if (alive) setLoading(false);
        });
    }, 220);
    return () => {
      alive = false;
      window.clearTimeout(handle);
    };
  }, [value, open, mode]);

  const q = value.trim().toLowerCase();
  const localHits =
    mode === "local" && q
      ? localItems
          .filter((item) => {
            const hay = `${item.label} ${item.meta || ""} ${item.id}`.toLowerCase();
            return hay.includes(q);
          })
          .slice(0, 8)
      : [];

  const recentHits =
    !q
      ? recent.slice(0, 6)
      : recent.filter((r) => r.toLowerCase().includes(q)).slice(0, 4);

  const hits: Hit[] = [
    ...recentHits.map((text) => ({ kind: "recent" as const, text })),
    ...catalogHits.map((card) => ({ kind: "catalog" as const, card })),
    ...localHits.map((item) => ({ kind: "local" as const, item })),
  ];

  const showPanel =
    open &&
    (hits.length > 0 || loading || (mode === "catalog" && value.trim().length >= 2));

  function syncBox() {
    const el = inputRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setBox({
      top: rect.bottom + 6,
      left: rect.left,
      width: Math.max(rect.width, 220),
    });
  }

  useLayoutEffect(() => {
    if (!showPanel) {
      setBox(null);
      return;
    }
    syncBox();
    function onReposition() {
      syncBox();
    }
    window.addEventListener("resize", onReposition);
    // capture scroll from any scrollable ancestor
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [showPanel, value, hits.length, loading]);

  useEffect(() => {
    function onDoc(event: MouseEvent) {
      const target = event.target as Node;
      if (rootRef.current?.contains(target) || panelRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    setActive(0);
  }, [value, open, catalogHits.length, localHits.length, recentHits.length]);

  function commitQuery(raw: string) {
    const next = raw.trim();
    onChange(next);
    if (next) setRecent(pushRecentSearch(recentScope, next));
    onCommit(next);
    setOpen(false);
  }

  function pick(hit: Hit) {
    if (hit.kind === "recent") {
      commitQuery(hit.text);
      return;
    }
    if (hit.kind === "catalog") {
      setRecent(pushRecentSearch(recentScope, hit.card.name));
      if (onPickCard) {
        onPickCard(hit.card);
        onChange(hit.card.name);
        setOpen(false);
        return;
      }
      commitQuery(hit.card.name);
      return;
    }
    setRecent(pushRecentSearch(recentScope, hit.item.label));
    if (onPickLocal) {
      onPickLocal(hit.item);
      onChange(hit.item.label);
      setOpen(false);
      return;
    }
    commitQuery(hit.item.label);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open || hits.length === 0) {
      if (event.key === "Escape") setOpen(false);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (i + 1) % hits.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (i - 1 + hits.length) % hits.length);
    } else if (event.key === "Enter" && open && hits[active]) {
      event.preventDefault();
      pick(hits[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const panel =
    mounted && showPanel && box
      ? createPortal(
          <div
            ref={panelRef}
            className="search-suggest-panel"
            id={listId}
            role="listbox"
            style={{
              top: box.top,
              left: box.left,
              width: box.width,
            }}
          >
            {recentHits.length > 0 ? (
              <p className="search-suggest-label">{t("search_suggested")}</p>
            ) : null}
            {hits.map((hit, index) => {
              const selected = index === active;
              if (hit.kind === "recent") {
                return (
                  <button
                    key={`r-${hit.text}`}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={`search-suggest-item ${selected ? "is-active" : ""}`}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => pick(hit)}
                  >
                    <span className="search-suggest-kind">{t("search_recent")}</span>
                    <span className="lot-name">{hit.text}</span>
                  </button>
                );
              }
              if (hit.kind === "local") {
                return (
                  <button
                    key={`l-${hit.item.id}`}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={`search-suggest-item ${selected ? "is-active" : ""}`}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => pick(hit)}
                  >
                    <span className="lot-name">{hit.item.label}</span>
                    {hit.item.meta ? (
                      <span className="lot-meta">{hit.item.meta}</span>
                    ) : null}
                  </button>
                );
              }
              const card = hit.card;
              return (
                <button
                  key={`c-${card.id}`}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`search-suggest-item has-art ${selected ? "is-active" : ""}`}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => pick(hit)}
                >
                  <span className="search-suggest-art">
                    <Image
                      src={card.image_url || "/kestrel-logo.png"}
                      alt=""
                      width={32}
                      height={44}
                    />
                  </span>
                  <span>
                    <span className="lot-name">{card.name}</span>
                    <span className="lot-meta">
                      {[card.set_name, formatMoney(card.price)]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </span>
                </button>
              );
            })}
            {loading ? (
              <p className="search-suggest-empty">{t("search_loading")}</p>
            ) : null}
            {!loading &&
            mode === "catalog" &&
            value.trim().length >= 2 &&
            catalogHits.length === 0 ? (
              <p className="search-suggest-empty">{t("search_no_hits")}</p>
            ) : null}
          </div>,
          document.body,
        )
      : null;

  return (
    <div className={`search-suggest${showPanel ? " is-open" : ""}`} ref={rootRef}>
      <input
        ref={inputRef}
        id={inputId}
        type="search"
        role="combobox"
        aria-expanded={showPanel}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label={ariaLabel}
        autoComplete="off"
        autoFocus={autoFocus}
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        onClick={() => setOpen(true)}
      />
      {panel}
    </div>
  );
}
