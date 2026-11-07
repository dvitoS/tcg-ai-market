"use client";

import { DeskLoading } from "@/components/DeskLoading";
import { useLocale } from "@/components/LocaleProvider";
import type { MessageKey } from "@/lib/i18n/messages";

/** Suspense-safe desk loading that picks EN/HR after LocaleProvider hydrates. */
export function LocalizedDeskLoading({
  labelKey,
  variant = "panel",
  skeletonCount = 6,
}: {
  labelKey: MessageKey;
  variant?: "panel" | "banner" | "rows";
  skeletonCount?: number;
}) {
  const { t } = useLocale();
  return (
    <DeskLoading
      label={t(labelKey)}
      variant={variant}
      skeletonCount={skeletonCount}
    />
  );
}
