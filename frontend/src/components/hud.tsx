import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

/** Background atmosphere layers — mounted once at the app root. */
export function DeckBackground() {
  return (
    <>
      <div className="deck-bg" />
      <div className="scanlines" />
    </>
  );
}

/** A blinking telemetry dot. */
export function LiveDot({ on = true }: { on?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`h-2 w-2 rounded-full ${
          on ? "bg-lime animate-pulse-dot shadow-[0_0_8px_2px_rgba(155,227,74,0.7)]" : "bg-haze"
        }`}
      />
      <span className={`text-[10px] tracking-[0.25em] ${on ? "text-lime" : "text-haze"}`}>
        {on ? "LIVE" : "OFFLINE"}
      </span>
    </span>
  );
}

/** HUD panel with corner ticks + label rail. */
export function Panel({
  label,
  accent = "amber",
  children,
  className = "",
  right,
}: {
  label?: string;
  accent?: "amber" | "cyan";
  children: React.ReactNode;
  className?: string;
  right?: React.ReactNode;
}) {
  return (
    <div
      className={`hud-frame bg-panel/70 backdrop-blur-sm shadow-panel ${className}`}
      style={{ ["--tw-edge" as string]: "#2a3543" }}
    >
      {(label || right) && (
        <div className="flex items-center justify-between border-b border-grid px-4 py-2">
          {label && (
            <span
              className={`font-display text-[11px] font-600 uppercase tracking-[0.3em] ${
                accent === "amber" ? "text-amber" : "text-cyan"
              }`}
            >
              {label}
            </span>
          )}
          {right}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

/** Animated count-up that eases toward a target whenever it changes. */
export function CountUp({
  value,
  decimals = 0,
  className = "",
}: {
  value: number;
  decimals?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const rafRef = useRef<number>();

  useEffect(() => {
    const from = fromRef.current;
    const to = value;
    const start = performance.now();
    const dur = 600;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (to - from) * eased);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
      else fromRef.current = to;
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current!);
  }, [value]);

  return (
    <span className={`tnum ${className}`}>
      {display.toLocaleString("fr-FR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
    </span>
  );
}

/** The hero metric tiles on the war-room. */
export function Gauge({
  label,
  value,
  unit,
  accent = "amber",
  index = 0,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  accent?: "amber" | "cyan" | "lime" | "rose";
  index?: number;
}) {
  const color = {
    amber: "text-amber",
    cyan: "text-cyan",
    lime: "text-lime",
    rose: "text-rose",
  }[accent];
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4 }}
      className="hud-frame relative overflow-hidden bg-panel/70 px-5 py-4 shadow-panel"
    >
      <div className="font-display text-[10px] uppercase tracking-[0.28em] text-ash">
        {label}
      </div>
      <div className={`mt-2 font-display text-4xl font-700 leading-none ${color}`}>
        {value}
        {unit && <span className="ml-1.5 text-sm font-500 text-haze">{unit}</span>}
      </div>
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-30"
        style={{
          background:
            accent === "cyan"
              ? "linear-gradient(90deg, transparent, #36e0e0, transparent)"
              : "linear-gradient(90deg, transparent, #ffb000, transparent)",
        }}
      />
    </motion.div>
  );
}

/** Thin labelled progress bar (used for leaderboards / shares). */
export function Bar({
  pct,
  accent = "amber",
}: {
  pct: number;
  accent?: "amber" | "cyan" | "lime";
}) {
  const bg = { amber: "bg-amber", cyan: "bg-cyan", lime: "bg-lime" }[accent];
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-grid">
      <div
        className={`h-full ${bg}`}
        style={{ width: `${Math.max(2, Math.min(100, pct))}%` }}
      />
    </div>
  );
}
