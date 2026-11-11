"use client";

import Link from "next/link";

import { useLocale } from "@/components/LocaleProvider";

/** Cold-user trust strip — plain proof, not the Pro calibration panel. */
export function TrustProof() {
  const { t } = useLocale();
  return (
    <section className="landing-trust" aria-labelledby="landing-trust-title">
      <h2 id="landing-trust-title" className="landing-path-title">
        {t("landing_trust_title")}
      </h2>
      <p className="landing-path-lede">{t("landing_trust_lede")}</p>
      <ul className="landing-trust-list">
        <li>{t("landing_trust_p1")}</li>
        <li>{t("landing_trust_p2")}</li>
        <li>{t("landing_trust_p3")}</li>
        <li>{t("landing_trust_p4")}</li>
      </ul>
      <p className="landing-trust-links">
        <Link href="/guides/kestrel-methodology">{t("landing_trust_method")}</Link>
        <span aria-hidden="true"> · </span>
        <Link href="/guides/pokemon-tcg-fair-value">{t("landing_trust_fair")}</Link>
      </p>
    </section>
  );
}
