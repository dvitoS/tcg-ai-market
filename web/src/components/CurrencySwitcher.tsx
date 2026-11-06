"use client";

import { useCurrency, type SpotCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";

const CODES: SpotCurrency[] = ["USD", "EUR"];

export function CurrencySwitcher() {
  const { currency, setCurrency, usdEur, fxFallback } = useCurrency();
  const { t } = useLocale();
  const title =
    usdEur != null
      ? t("fx_rate_tip", { rate: usdEur.toFixed(4) }) +
        (fxFallback ? ` (${t("fx_fallback")})` : "")
      : t("fx_loading");

  return (
    <div
      className="locale-switcher currency-switcher"
      role="group"
      aria-label={t("fx_currency_aria")}
      title={title}
    >
      {CODES.map((code) => (
        <button
          key={code}
          type="button"
          className={`locale-btn${currency === code ? " is-active" : ""}`}
          aria-pressed={currency === code}
          onClick={() => setCurrency(code)}
        >
          {code}
        </button>
      ))}
    </div>
  );
}
