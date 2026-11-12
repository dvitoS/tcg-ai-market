"use client";

import { PUBLIC_LOCALES, type Locale } from "@/lib/i18n/messages";
import { useLocale } from "@/components/LocaleProvider";

const LABELS: Record<Locale, string> = {
  en: "EN",
  hr: "HR",
};

export function LocaleSwitcher() {
  const { locale, setLocale } = useLocale();

  // Soft launch: EN only — keep the component mounted so header layout stays stable
  // if PUBLIC_LOCALES grows again, but hide the control while there's nothing to pick.
  if (PUBLIC_LOCALES.length < 2) return null;

  return (
    <div className="locale-switcher" role="group" aria-label="Language">
      {PUBLIC_LOCALES.map((code) => (
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
