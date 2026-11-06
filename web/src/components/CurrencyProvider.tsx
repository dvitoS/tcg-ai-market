"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useLocale } from "@/components/LocaleProvider";
import { apiUrl, formatMoney as formatMoneyRaw } from "@/lib/api";

export type SpotCurrency = "USD" | "EUR";

export const CURRENCY_STORAGE_KEY = "kestrel_spot_currency";

type FxQuote = {
  usd_eur: number;
  as_of?: string | null;
  source: string;
  fallback: boolean;
};

type CurrencyContextValue = {
  currency: SpotCurrency;
  setCurrency: (c: SpotCurrency) => void;
  usdEur: number | null;
  fxFallback: boolean;
  fxAsOf: string | null;
  /** Format a USD spot in the active Soft Ink display currency. */
  formatSpot: (value?: number | null, digits?: number) => string;
};

const CurrencyContext = createContext<CurrencyContextValue | null>(null);

function readStoredCurrency(localeDefault: SpotCurrency): SpotCurrency {
  if (typeof window === "undefined") return localeDefault;
  const raw = window.localStorage.getItem(CURRENCY_STORAGE_KEY);
  if (raw === "USD" || raw === "EUR") return raw;
  return localeDefault;
}

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const { locale } = useLocale();
  const localeDefault: SpotCurrency = locale === "hr" ? "EUR" : "USD";
  const [currency, setCurrencyState] = useState<SpotCurrency>("USD");
  const [hydrated, setHydrated] = useState(false);
  const [usdEur, setUsdEur] = useState<number | null>(null);
  const [fxFallback, setFxFallback] = useState(false);
  const [fxAsOf, setFxAsOf] = useState<string | null>(null);

  useEffect(() => {
    setCurrencyState(readStoredCurrency(localeDefault));
    setHydrated(true);
  }, [localeDefault]);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(CURRENCY_STORAGE_KEY, currency);
  }, [currency, hydrated]);

  useEffect(() => {
    let alive = true;
    void fetch(apiUrl("/api/fx"), {
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`FX ${res.status}`);
        return res.json() as Promise<FxQuote>;
      })
      .then((quote) => {
        if (!alive) return;
        const rate = Number(quote.usd_eur);
        setUsdEur(Number.isFinite(rate) && rate > 0 ? rate : null);
        setFxFallback(Boolean(quote.fallback));
        setFxAsOf(quote.as_of || null);
      })
      .catch(() => {
        if (!alive) return;
        setUsdEur(0.92);
        setFxFallback(true);
        setFxAsOf(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  const setCurrency = useCallback((next: SpotCurrency) => {
    setCurrencyState(next);
  }, []);

  const formatSpot = useCallback(
    (value?: number | null, digits = 2) => {
      if (value == null || Number.isNaN(Number(value))) {
        return formatMoneyRaw(null, currency, digits);
      }
      const usd = Number(value);
      if (currency === "EUR" && usdEur != null) {
        return formatMoneyRaw(usd * usdEur, "EUR", digits);
      }
      return formatMoneyRaw(usd, "USD", digits);
    },
    [currency, usdEur],
  );

  const value = useMemo(
    () => ({
      currency,
      setCurrency,
      usdEur,
      fxFallback,
      fxAsOf,
      formatSpot,
    }),
    [currency, setCurrency, usdEur, fxFallback, fxAsOf, formatSpot],
  );

  return (
    <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>
  );
}

export function useCurrency(): CurrencyContextValue {
  const ctx = useContext(CurrencyContext);
  if (!ctx) {
    throw new Error("useCurrency must be used within CurrencyProvider");
  }
  return ctx;
}
