"use client";

import type { ReactNode } from "react";

export type MarketSource = "ebay" | "tcgplayer" | "cardmarket";

const ICONS: Record<MarketSource, ReactNode> = {
  ebay: (
    <svg className="mkt-tab-icon" viewBox="0 0 48 16" aria-hidden>
      <text
        x="0"
        y="13"
        fontFamily="system-ui,sans-serif"
        fontWeight="800"
        fontSize="14"
        letterSpacing="-0.5"
      >
        <tspan fill="#e53238">e</tspan>
        <tspan fill="#0064d2">b</tspan>
        <tspan fill="#f5af02">a</tspan>
        <tspan fill="#86b817">y</tspan>
      </text>
    </svg>
  ),
  tcgplayer: (
    <svg className="mkt-tab-icon mkt-tab-icon-tcp" viewBox="0 0 20 20" aria-hidden>
      <rect x="2" y="3" width="5" height="12" rx="1" fill="#f5c518" />
      <rect x="7.5" y="2" width="5" height="14" rx="1" fill="#3b82f6" />
      <path
        d="M9.2 6.2 L11.3 9.2 L9.2 12.2 L10.2 9.2 Z"
        fill="#fff"
      />
      <rect x="13" y="3.5" width="5" height="12" rx="1" fill="#ef4444" />
    </svg>
  ),
  cardmarket: (
    <svg className="mkt-tab-icon mkt-tab-icon-cm" viewBox="0 0 20 20" aria-hidden>
      <path
        fill="#3b82f6"
        d="M3 14.5 L10 4.5 L17 14.5 Z"
        opacity="0.95"
      />
      <path fill="#60a5fa" d="M6.2 14.5 L10 8.2 L13.8 14.5 Z" />
      <rect x="8.6" y="12.2" width="2.8" height="2.6" rx="0.3" fill="#93c5fd" />
    </svg>
  ),
};

const LABELS: Record<MarketSource, string> = {
  ebay: "eBay",
  tcgplayer: "TCGplayer",
  cardmarket: "Cardmarket",
};

export function MarketSourceTabs({
  sources,
  value,
  onChange,
  ariaLabel,
}: {
  sources: MarketSource[];
  value: MarketSource;
  onChange: (next: MarketSource) => void;
  ariaLabel: string;
}) {
  return (
    <div className="mkt-tabs" role="tablist" aria-label={ariaLabel}>
      {sources.map((src) => {
        const active = value === src;
        return (
          <button
            key={src}
            type="button"
            role="tab"
            aria-selected={active}
            className={`mkt-tab${active ? " is-active" : ""}`}
            onClick={() => onChange(src)}
          >
            {ICONS[src]}
            <span className="mkt-tab-label">{LABELS[src]}</span>
          </button>
        );
      })}
    </div>
  );
}
