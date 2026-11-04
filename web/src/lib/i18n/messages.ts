export type Locale = "en" | "hr";

export const LOCALES: Locale[] = ["en", "hr"];

export const LOCALE_STORAGE_KEY = "kestrel_locale";

export type MessageKey =
  | "nav_browse"
  | "nav_signals"
  | "nav_portfolio"
  | "nav_scanner"
  | "nav_dealer"
  | "nav_pro"
  | "brand_tagline"
  | "auth_sign_in"
  | "auth_sign_out"
  | "nav_open_menu"
  | "nav_close_menu"
  | "nav_primary"
  | "nav_mobile"
  | "landing_headline"
  | "landing_lede"
  | "landing_cta_market"
  | "landing_cta_pro"
  | "landing_follow_title"
  | "landing_follow_lede"
  | "landing_follow_link"
  | "explore_eyebrow"
  | "explore_title"
  | "explore_lede"
  | "catalog_mode"
  | "catalog_browse"
  | "catalog_signals"
  | "explore_search_ph"
  | "explore_search_aria"
  | "explore_search_btn"
  | "explore_clear"
  | "explore_set"
  | "explore_all_sets"
  | "explore_signal"
  | "explore_all"
  | "explore_min"
  | "explore_max"
  | "explore_any"
  | "explore_results"
  | "explore_demo"
  | "explore_updating"
  | "explore_empty"
  | "explore_load_more"
  | "signal_buy"
  | "signal_sell"
  | "signal_hold";

type Dictionary = Record<MessageKey, string>;

const en: Dictionary = {
  nav_browse: "Browse",
  nav_signals: "AI signals",
  nav_portfolio: "Portfolio",
  nav_scanner: "Scanner",
  nav_dealer: "Dealer",
  nav_pro: "Pro",
  brand_tagline: "Spot. Signal. Act.",
  auth_sign_in: "Sign in",
  auth_sign_out: "Sign out",
  nav_open_menu: "Open menu",
  nav_close_menu: "Close menu",
  nav_primary: "Primary",
  nav_mobile: "Mobile",
  landing_headline: "Spot. Signal. Act.",
  landing_lede:
    "Pokémon TCG market prices and AI forecasts — browse, watch, and move before the print run cools.",
  landing_cta_market: "Open market",
  landing_cta_pro: "Soft Pro",
  landing_follow_title: "From signal to desk",
  landing_follow_lede:
    "One path: browse the board, read the AI explain, hold a portfolio, scan movers, export dealer CSV.",
  landing_follow_link: "Jump to AI signals →",
  explore_eyebrow: "Browse market",
  explore_title: "Market",
  explore_lede: "Pokémon TCG prices and AI signals — art-first, mobile-ready.",
  catalog_mode: "Catalog mode",
  catalog_browse: "Browse",
  catalog_signals: "AI signals",
  explore_search_ph: "Search name, set, or id…",
  explore_search_aria: "Search cards",
  explore_search_btn: "Search",
  explore_clear: "Clear",
  explore_set: "Set",
  explore_all_sets: "All sets",
  explore_signal: "Signal",
  explore_all: "All",
  explore_min: "Min $",
  explore_max: "Max $",
  explore_any: "Any",
  explore_results: "{n} cards",
  explore_demo: "demo seed",
  explore_updating: "updating…",
  explore_empty: "No cards match these filters. Try clearing price or set.",
  explore_load_more: "Load more",
  signal_buy: "BUY",
  signal_sell: "SELL",
  signal_hold: "HOLD",
};

const hr: Dictionary = {
  nav_browse: "Pregled",
  nav_signals: "AI signali",
  nav_portfolio: "Portfelj",
  nav_scanner: "Skener",
  nav_dealer: "Dealer",
  nav_pro: "Pro",
  brand_tagline: "Uoči. Signal. Djeluj.",
  auth_sign_in: "Prijava",
  auth_sign_out: "Odjava",
  nav_open_menu: "Otvori izbornik",
  nav_close_menu: "Zatvori izbornik",
  nav_primary: "Glavna navigacija",
  nav_mobile: "Mobilna navigacija",
  landing_headline: "Uoči. Signal. Djeluj.",
  landing_lede:
    "Pokémon TCG tržišne cijene i AI prognoze — pregledaj, prati i reagraj dok je otisak još vruć.",
  landing_cta_market: "Otvori tržište",
  landing_cta_pro: "Soft Pro",
  landing_follow_title: "Od signala do stola",
  landing_follow_lede:
    "Jedan put: pregledaj board, pročitaj AI explain, vodi portfelj, skeniraj movers, izvezi dealer CSV.",
  landing_follow_link: "Idi na AI signale →",
  explore_eyebrow: "Pregled tržišta",
  explore_title: "Tržište",
  explore_lede: "Pokémon TCG cijene i AI signali — art-first, spremno za mobitel.",
  catalog_mode: "Način kataloga",
  catalog_browse: "Pregled",
  catalog_signals: "AI signali",
  explore_search_ph: "Traži ime, set ili id…",
  explore_search_aria: "Pretraži karte",
  explore_search_btn: "Traži",
  explore_clear: "Očisti",
  explore_set: "Set",
  explore_all_sets: "Svi setovi",
  explore_signal: "Signal",
  explore_all: "Sve",
  explore_min: "Min $",
  explore_max: "Max $",
  explore_any: "Bilo koji",
  explore_results: "{n} karata",
  explore_demo: "demo seed",
  explore_updating: "osvježavam…",
  explore_empty: "Nema karata za ove filtere. Pokušaj očistiti cijenu ili set.",
  explore_load_more: "Učitaj još",
  signal_buy: "KUPI",
  signal_sell: "PRODAJ",
  signal_hold: "DRŽI",
};

export const MESSAGES: Record<Locale, Dictionary> = { en, hr };

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "en" || value === "hr";
}

export function translate(
  locale: Locale,
  key: MessageKey,
  params?: Record<string, string | number>,
): string {
  const template = MESSAGES[locale][key] ?? MESSAGES.en[key] ?? key;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) =>
    params[name] != null ? String(params[name]) : `{${name}}`,
  );
}

export function signalLabel(locale: Locale, signal?: string | null): string {
  const key = (signal || "").toUpperCase();
  if (key === "BUY" || key === "KUPI") return translate(locale, "signal_buy");
  if (key === "SELL" || key === "PRODAJ") return translate(locale, "signal_sell");
  if (key === "HOLD" || key === "DRŽI" || key === "DRZI") {
    return translate(locale, "signal_hold");
  }
  return signal || "—";
}
