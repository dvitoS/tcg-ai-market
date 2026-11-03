"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import {
  addWatchlistCard,
  fetchWatchStatus,
  removeWatchlistCard,
} from "@/lib/api";

export function WatchToggle({ cardId }: { cardId: string }) {
  const { user, ensureDemoSession } = useAuth();
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
    setBusy(true);
    try {
      if (!user) {
        await ensureDemoSession();
      }
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
