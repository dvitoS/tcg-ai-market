"use client";

import { useEffect, useRef } from "react";

type Ribbon = {
  amp: number;
  thick: number;
  speed: number;
  phase: number;
  yBase: number;
  rgb: string;
  alpha: number;
};

type Plume = {
  x: number;
  y: number;
  r: number;
  life: number;
  speed: number;
  driftX: number;
  driftY: number;
  rgb: string;
  lobes: number;
};

/**
 * Soft Ink hero — ink-in-water copper plumes + soft tide ribbons.
 * Canvas so the motion is unmistakable; deliberately not particle/neon.
 */
export function SoftInkWash() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let raf = 0;
    let running = true;
    let w = 0;
    let h = 0;
    let dpr = 1;
    const start = performance.now();

    const ribbons: Ribbon[] = [
      {
        amp: 0.055,
        thick: 0.2,
        speed: 0.16,
        phase: 0.4,
        yBase: 0.42,
        rgb: "192,122,58",
        alpha: 0.22,
      },
      {
        amp: 0.07,
        thick: 0.14,
        speed: 0.23,
        phase: 1.8,
        yBase: 0.55,
        rgb: "224,180,120",
        alpha: 0.18,
      },
      {
        amp: 0.045,
        thick: 0.24,
        speed: 0.12,
        phase: 2.9,
        yBase: 0.64,
        rgb: "140,82,42",
        alpha: 0.16,
      },
    ];

    const plumes: Plume[] = [
      {
        x: 0.72,
        y: 0.32,
        r: 0.28,
        life: 0,
        speed: 0.055,
        driftX: 0.03,
        driftY: 0.02,
        rgb: "212,165,116",
        lobes: 3,
      },
      {
        x: 0.58,
        y: 0.58,
        r: 0.22,
        life: 0.33,
        speed: 0.042,
        driftX: -0.025,
        driftY: 0.015,
        rgb: "192,122,58",
        lobes: 4,
      },
      {
        x: 0.86,
        y: 0.48,
        r: 0.2,
        life: 0.66,
        speed: 0.048,
        driftX: -0.02,
        driftY: -0.02,
        rgb: "232,196,140",
        lobes: 3,
      },
      {
        x: 0.48,
        y: 0.28,
        r: 0.18,
        life: 0.15,
        speed: 0.038,
        driftX: 0.018,
        driftY: 0.03,
        rgb: "168,104,55",
        lobes: 5,
      },
      {
        x: 0.78,
        y: 0.72,
        r: 0.24,
        life: 0.5,
        speed: 0.05,
        driftX: 0.022,
        driftY: -0.018,
        rgb: "200,140,80",
        lobes: 4,
      },
      {
        x: 0.64,
        y: 0.18,
        r: 0.16,
        life: 0.82,
        speed: 0.06,
        driftX: -0.03,
        driftY: 0.01,
        rgb: "224,170,110",
        lobes: 3,
      },
    ];

    function resize() {
      const parent = canvas.parentElement;
      if (!parent) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = parent.clientWidth;
      h = parent.clientHeight;
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function drawRibbon(r: Ribbon, t: number) {
      if (w < 1 || h < 1) return;
      const steps = Math.max(40, Math.floor(w / 16));
      ctx.beginPath();
      for (let i = 0; i <= steps; i++) {
        const x = (i / steps) * w;
        const n =
          Math.sin(i * 0.14 + t * r.speed + r.phase) * r.amp +
          Math.sin(i * 0.05 - t * r.speed * 0.55 + r.phase) * r.amp * 0.5;
        const y = (r.yBase + n) * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      for (let i = steps; i >= 0; i--) {
        const x = (i / steps) * w;
        const n =
          Math.sin(i * 0.14 + t * r.speed + r.phase) * r.amp +
          Math.sin(i * 0.05 - t * r.speed * 0.55 + r.phase) * r.amp * 0.5;
        const y = (r.yBase + n + r.thick) * h;
        ctx.lineTo(x, y);
      }
      ctx.closePath();
      const g = ctx.createLinearGradient(0, h * r.yBase, w, h * (r.yBase + r.thick));
      g.addColorStop(0, `rgba(${r.rgb},0)`);
      g.addColorStop(0.25, `rgba(${r.rgb},${r.alpha})`);
      g.addColorStop(0.55, `rgba(${r.rgb},${r.alpha * 0.85})`);
      g.addColorStop(1, `rgba(${r.rgb},0)`);
      ctx.fillStyle = g;
      ctx.fill();
    }

    function drawPlume(p: Plume, t: number) {
      if (w < 1 || h < 1) return;
      const cycle = (p.life + t * p.speed) % 1;
      // Ease in/out bloom — ink unfurls then thins.
      const bloom = Math.sin(cycle * Math.PI);
      if (bloom < 0.04) return;

      const cx = (p.x + Math.sin(t * 0.2 + p.life * 6) * p.driftX) * w;
      const cy = (p.y + Math.cos(t * 0.17 + p.life * 4) * p.driftY + cycle * 0.06) * h;
      const base = p.r * Math.min(w, h) * (0.45 + bloom * 1.15);

      // Soft core
      const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, base);
      core.addColorStop(0, `rgba(${p.rgb},${0.55 * bloom})`);
      core.addColorStop(0.35, `rgba(${p.rgb},${0.28 * bloom})`);
      core.addColorStop(0.7, `rgba(${p.rgb},${0.1 * bloom})`);
      core.addColorStop(1, `rgba(${p.rgb},0)`);
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(cx, cy, base, 0, Math.PI * 2);
      ctx.fill();

      // Filaments / lobes — the “ink in water” signature
      for (let i = 0; i < p.lobes; i++) {
        const ang = (i / p.lobes) * Math.PI * 2 + t * 0.35 + p.life * 8;
        const reach = base * (0.85 + 0.55 * Math.sin(t * 0.9 + i + p.life));
        const lx = cx + Math.cos(ang) * reach * 0.75;
        const ly = cy + Math.sin(ang) * reach * 0.55;
        const lr = base * (0.35 + 0.2 * bloom);
        const lobe = ctx.createRadialGradient(lx, ly, 0, lx, ly, lr);
        lobe.addColorStop(0, `rgba(${p.rgb},${0.4 * bloom})`);
        lobe.addColorStop(0.55, `rgba(${p.rgb},${0.12 * bloom})`);
        lobe.addColorStop(1, `rgba(${p.rgb},0)`);
        ctx.fillStyle = lobe;
        ctx.beginPath();
        ctx.arc(lx, ly, lr, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function drawFrame(now: number) {
      if (!running && !reduce) return;
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, w, h);

      // Warm field so copper reads on the dark hero plane.
      const field = ctx.createRadialGradient(
        w * 0.74,
        h * 0.4,
        0,
        w * 0.68,
        h * 0.45,
        Math.max(w, h) * 0.78,
      );
      field.addColorStop(0, "rgba(192,122,58,0.2)");
      field.addColorStop(0.5, "rgba(90,58,32,0.08)");
      field.addColorStop(1, "rgba(10,9,8,0)");
      ctx.fillStyle = field;
      ctx.fillRect(0, 0, w, h);

      ctx.globalCompositeOperation = "lighter";
      for (const r of ribbons) drawRibbon(r, t);
      for (const p of plumes) drawPlume(p, t);
      ctx.globalCompositeOperation = "source-over";
    }

    function loop(now: number) {
      drawFrame(now);
      if (!reduce && running) raf = window.requestAnimationFrame(loop);
    }

    function onVisibility() {
      if (document.hidden) {
        running = false;
        if (raf) cancelAnimationFrame(raf);
      } else {
        running = true;
        if (!reduce) raf = window.requestAnimationFrame(loop);
        else drawFrame(performance.now());
      }
    }

    resize();
    drawFrame(performance.now());
    if (!reduce) raf = window.requestAnimationFrame(loop);

    const ro = new ResizeObserver(resize);
    if (canvas.parentElement) ro.observe(canvas.parentElement);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("resize", resize);

    return () => {
      running = false;
      if (raf) cancelAnimationFrame(raf);
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <div className="soft-ink-wash" aria-hidden="true">
      <canvas ref={canvasRef} className="soft-ink-wash-canvas" />
      <div className="soft-ink-wash-vignette" />
    </div>
  );
}
