"use client";

import { CardSkeletonGrid } from "@/components/CardSkeletonGrid";

type Variant = "panel" | "banner" | "rows";

export function DeskLoading({
  label,
  variant = "panel",
  skeletonCount = 6,
}: {
  label: string;
  variant?: Variant;
  skeletonCount?: number;
}) {
  if (variant === "banner") {
    return (
      <div className="loading-banner" role="status" aria-live="polite">
        <span className="desk-spinner" aria-hidden />
        <span>{label}</span>
      </div>
    );
  }

  return (
    <div className="desk-loading" role="status" aria-live="polite">
      <div className="desk-loading-copy">
        <span className="desk-spinner" aria-hidden />
        <p>{label}</p>
      </div>
      {variant === "rows" || variant === "panel" ? (
        <CardSkeletonGrid count={skeletonCount} />
      ) : null}
    </div>
  );
}
