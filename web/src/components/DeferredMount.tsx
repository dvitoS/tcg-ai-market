"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Mount children only once the sentinel enters (near) the viewport.
 * Used to defer below-fold detail panels (Grading EV, eBay) off the critical path.
 */
export function DeferredMount({
  children,
  rootMargin = "240px 0px",
  fallback = null,
}: {
  children: ReactNode;
  rootMargin?: string;
  fallback?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setShow(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShow(true);
          io.disconnect();
        }
      },
      { rootMargin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [rootMargin]);

  return <div ref={ref}>{show ? children : fallback}</div>;
}
