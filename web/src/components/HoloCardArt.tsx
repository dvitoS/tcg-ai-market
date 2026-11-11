"use client";

import Image from "next/image";
import {
  useCallback,
  useEffect,
  useRef,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { onCardImageError } from "@/lib/cardImage";
import type { FoilMode } from "@/lib/foilMode";

const TILT_MAX = 14;

/**
 * Soft Ink card art with original tilt + foil overlays.
 * Inspired by interactive holo demos — not a fork of GPL poke-holo CSS.
 */
export function HoloCardArt({
  cardId,
  name,
  image,
  foil,
  priority = false,
  width = 420,
  height = 586,
  sizes = "(max-width: 720px) 55vw, 200px",
  className = "",
  /** Fill parent frame (landing hero) instead of natural aspect height. */
  fillFrame = false,
}: {
  cardId: string;
  name: string;
  image: string;
  foil: FoilMode;
  priority?: boolean;
  width?: number;
  height?: number;
  sizes?: string;
  className?: string;
  fillFrame?: boolean;
}) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const reduceRef = useRef(false);

  useEffect(() => {
    reduceRef.current = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
  }, []);

  // Idle shine on first paint so Soft Ink client nav shows foil without refresh.
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    if (foil === "holo" || foil === "reverse") {
      frame.style.setProperty("--go", reduceRef.current ? "0.22" : "0.42");
      frame.style.setProperty("--mx", "42%");
      frame.style.setProperty("--my", "38%");
    } else {
      frame.style.removeProperty("--go");
      frame.style.removeProperty("--mx");
      frame.style.removeProperty("--my");
    }
    frame.style.removeProperty("--rx");
    frame.style.removeProperty("--ry");
    frame.classList.remove("is-tilting");
  }, [foil, cardId]);

  const resetTilt = useCallback(() => {
    const frame = frameRef.current;
    if (!frame) return;
    frame.style.removeProperty("--rx");
    frame.style.removeProperty("--ry");
    frame.classList.remove("is-tilting");
    // Keep a soft idle foil after pointer leaves (don't kill shine).
    if (foil === "holo" || foil === "reverse") {
      frame.style.setProperty("--go", reduceRef.current ? "0.22" : "0.42");
      frame.style.setProperty("--mx", "48%");
      frame.style.setProperty("--my", "40%");
    } else {
      frame.style.removeProperty("--mx");
      frame.style.removeProperty("--my");
      frame.style.removeProperty("--go");
    }
  }, [foil]);

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      if (reduceRef.current) return;
      const frame = frameRef.current;
      if (!frame) return;
      const rect = frame.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) return;
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;
      const ry = (x - 0.5) * 2 * TILT_MAX;
      const rx = (0.5 - y) * 2 * TILT_MAX;
      frame.classList.add("is-tilting");
      frame.style.setProperty("--ry", `${ry.toFixed(2)}deg`);
      frame.style.setProperty("--rx", `${rx.toFixed(2)}deg`);
      frame.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`);
      frame.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
      frame.style.setProperty("--go", "1");
    },
    [],
  );

  const foilClass =
    foil === "holo"
      ? "is-foil-holo"
      : foil === "reverse"
        ? "is-foil-reverse"
        : "is-foil-none";

  return (
    <div
      ref={frameRef}
      className={`holo-card-art ${foilClass} ${className}`.trim()}
      onPointerMove={onPointerMove}
      onPointerLeave={resetTilt}
      onPointerCancel={resetTilt}
    >
      <Image
        src={image}
        alt={name}
        width={width}
        height={height}
        priority={priority}
        className={`holo-card-art-img${fillFrame ? " is-fill" : ""}`}
        sizes={sizes}
        style={
          fillFrame
            ? { width: "100%", height: "100%", objectFit: "cover" }
            : { width: "100%", height: "auto" }
        }
        onError={(event) => onCardImageError(event, cardId)}
      />
      <span className="holo-card-art-foil" aria-hidden="true" />
      <span className="holo-card-art-glare" aria-hidden="true" />
      <span className="holo-card-art-sheen" aria-hidden="true" />
    </div>
  );
}
