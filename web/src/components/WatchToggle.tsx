"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import {
  addWatchlistCard,
  fetchWatchStatus,
  removeWatchlistCard,
} from "@/lib/api";

export function WatchToggle({ cardId }: { cardId: string }) {
  const { user } = useAuth();
  const [watched, setWatched] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        if (!user) {
          if (alive) setWatched(false);
          return;
        }
        const on = await fetchWatchStatus(cardId);
        if (alive) setWatched(on);
      } catch {
        if (alive) setWatched(false);
      }
    }
    void load();
    return () => {
      alive = false;
    };
  }, [cardId, user]);

  async function toggle() {
    if (!user) return;
    setBusy(true);
    try {
      if (watched) {
        await removeWatchlistCard(cardId);
        setWatched(false);
      } else {
        await addWatchlistCard(cardId);
        setWatched(true);
      }
    } catch {
      // keep previous state
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <Link href="/portfolio" className="btn-ghost watch-toggle">
        Sign in to watch
      </Link>
    );
  }

  return (
    <button
      type="button"
      className={`btn-ghost watch-toggle ${watched ? "is-on" : ""}`}
      disabled={busy}
      onClick={() => void toggle()}
    >
      {watched ? "Watching" : "Add to watchlist"}
    </button>
  );
}
