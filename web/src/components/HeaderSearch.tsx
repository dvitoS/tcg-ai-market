"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { useLocale } from "@/components/LocaleProvider";
import { SearchSuggest } from "@/components/SearchSuggest";
import type { CatalogCard } from "@/lib/types";

type Props = {
  /** Close mobile drawer after navigate. */
  onNavigated?: () => void;
  className?: string;
};

export function HeaderSearch({ onNavigated, className }: Props) {
  const { t } = useLocale();
  const router = useRouter();
  const [query, setQuery] = useState("");

  function goBrowse(raw: string) {
    const q = raw.trim();
    onNavigated?.();
    if (!q) {
      router.push("/browse");
      return;
    }
    router.push(`/browse?q=${encodeURIComponent(q)}`);
  }

  function goCard(card: CatalogCard) {
    onNavigated?.();
    setQuery(card.name);
    router.push(`/cards/${encodeURIComponent(card.id)}`);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    goBrowse(query);
  }

  return (
    <form
      className={`header-search${className ? ` ${className}` : ""}`}
      onSubmit={onSubmit}
      role="search"
    >
      <SearchSuggest
        value={query}
        onChange={setQuery}
        onCommit={goBrowse}
        onPickCard={goCard}
        placeholder={t("nav_search_ph")}
        ariaLabel={t("nav_search_aria")}
        recentScope="header"
      />
    </form>
  );
}
