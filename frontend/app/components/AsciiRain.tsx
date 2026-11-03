"use client";

import { useEffect, useRef, useState } from "react";

const GLYPHS = "│┃|/\\<>+×01GNESIS".split("");

export default function AsciiRain({ hidden, onPanel }: { hidden: boolean; onPanel: () => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [fps, setFps] = useState(16);

  useEffect(() => {
    if (hidden) return;
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const W = (canvas.width = window.innerWidth);
    const H = (canvas.height = window.innerHeight);
    const colW = 22;
    const cols = Math.floor(W / colW);
    const drops = Array.from({ length: cols }, () =>
      Math.floor(Math.random() * (H / colW))
    );

    let frames = 0;
    let raf = 0;
    let last = performance.now();

    const fpsCb = (n: number) => setFps(n);
    const draw = () => {
      ctx.fillStyle = "rgba(10, 13, 18, 0.12)";
      ctx.fillRect(0, 0, W, H);
      ctx.font = "15px ui-monospace, Menlo, monospace";
      for (let i = 0; i < cols; i++) {
        const ch = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
        const head = Math.random() < 0.02;
        ctx.fillStyle = head ? "rgba(158, 206, 106, 0.85)" : "rgba(110, 140, 120, 0.4)";
        ctx.fillText(ch, i * colW, drops[i] * colW);
        if (drops[i] * colW > H && Math.random() > 0.976) drops[i] = 0;
        drops[i]++;
      }
      frames++;
      const now = performance.now();
      if (now - last >= 1000) {
        fpsCb(Math.round((frames * 1000) / (now - last)));
        frames = 0;
        last = now;
      }
      raf = requestAnimationFrame(draw);
    };

    if (reduced) {
      ctx.fillStyle = "#0a0d12";
      ctx.fillRect(0, 0, W, H);
      fpsCb(0);
    } else {
      ctx.fillStyle = "#0a0d12";
      ctx.fillRect(0, 0, W, H);
      raf = requestAnimationFrame(draw);
    }
    return () => cancelAnimationFrame(raf);
  }, [hidden]);

  return (
    <>
      {!hidden && <canvas ref={ref} className="rain" aria-hidden />}
      <div className="hud">
        <span>{fps} FPS</span>
        <button type="button" onClick={onPanel}>
          Control Panel [+]
        </button>
      </div>
    </>
  );
}
