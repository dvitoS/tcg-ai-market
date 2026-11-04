"use client";

import { LOCALES, type Locale } from "@/lib/i18n/messages";
import { useLocale } from "@/components/LocaleProvider";

const LABELS: Record<Locale, string> = {
  en: "EN",
  hr: "HR",
};

export function LocaleSwitcher() {
  const { locale, setLocale } = useLocale();

  return (
    <div className="locale-switcher" role="group" aria-label="Language">
      {LOCALES.map((code) => (
        <button
          key={code}
          type="button"
          className={`locale-btn${locale === code ? " is-active" : ""}`}
          aria-pressed={locale === code}
          onClick={() => setLocale(code)}
        >
          {LABELS[code]}
        </button>
      ))}
    </div>
  );
}
