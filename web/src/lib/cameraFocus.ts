/** Best-effort continuous + tap-to-focus for getUserMedia tracks. */

type FocusCapable = MediaTrackCapabilities & {
  focusMode?: string[];
  pointsOfInterest?: boolean | object;
};

type FocusConstraint = MediaTrackConstraintSet & {
  focusMode?: string | ConstrainDOMString;
  pointsOfInterest?: Array<{ x: number; y: number }>;
};

function videoTrack(stream: MediaStream | null): MediaStreamTrack | null {
  return stream?.getVideoTracks?.()[0] ?? null;
}

function capabilities(track: MediaStreamTrack): FocusCapable {
  try {
    return (track.getCapabilities?.() || {}) as FocusCapable;
  } catch {
    return {};
  }
}

/** Prefer continuous AF once the rear camera is live. */
export async function enableContinuousFocus(
  stream: MediaStream | null,
): Promise<boolean> {
  const track = videoTrack(stream);
  if (!track || typeof track.applyConstraints !== "function") return false;
  const caps = capabilities(track);
  const modes = caps.focusMode || [];
  const preferred = modes.includes("continuous")
    ? "continuous"
    : modes.includes("single-shot")
      ? "single-shot"
      : null;
  if (!preferred) return false;
  try {
    const advanced: FocusConstraint = { focusMode: preferred };
    await track.applyConstraints({ advanced: [advanced] });
    return true;
  } catch {
    try {
      await track.applyConstraints({
        focusMode: preferred,
      } as MediaTrackConstraints);
      return true;
    } catch {
      return false;
    }
  }
}

/**
 * Tap-to-focus at a point in the video element (client coordinates).
 * Uses pointsOfInterest when the device exposes it; otherwise triggers
 * a single-shot autofocus cycle.
 */
export async function focusAtPoint(
  stream: MediaStream | null,
  video: HTMLVideoElement,
  clientX: number,
  clientY: number,
): Promise<boolean> {
  const track = videoTrack(stream);
  if (!track || typeof track.applyConstraints !== "function") return false;

  const rect = video.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return false;
  const x = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  const y = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));

  const caps = capabilities(track);
  const modes = caps.focusMode || [];
  const supportsPoi = "pointsOfInterest" in caps;
  const advanced: FocusConstraint = {};

  if (supportsPoi) {
    advanced.pointsOfInterest = [{ x, y }];
  }
  if (modes.includes("single-shot")) {
    advanced.focusMode = "single-shot";
  } else if (modes.includes("continuous")) {
    advanced.focusMode = "continuous";
  } else if (modes.includes("manual")) {
    // Nudge manual focus distance if exposed — many phones still refocus.
    advanced.focusMode = "manual";
  }

  if (!advanced.focusMode && !advanced.pointsOfInterest) return false;

  try {
    await track.applyConstraints({ advanced: [advanced] });
    return true;
  } catch {
    if (!advanced.focusMode) return false;
    try {
      await track.applyConstraints({
        focusMode: advanced.focusMode,
      } as MediaTrackConstraints);
      return true;
    } catch {
      return false;
    }
  }
}
