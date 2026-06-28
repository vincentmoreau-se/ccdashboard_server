import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

/** Background atmosphere layers — mounted once at the app root. */
export function DeckBackground() {
  return (
    <>
      <div className="deck-bg" />
      <div className="deck-sweep" />
      <div className="scanlines" />
    </>
  );
}

/**
 * One-shot "power-on" overlay: HUD boot lines + filling progress bar, then
 * fades away. Purely cosmetic — unmounts after ~1s. Skipped under
 * prefers-reduced-motion so it never flashes for those users.
 */
export function BootOverlay() {
  const reduce = useReducedMotion();
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (reduce) return;
    const t = setTimeout(() => setDone(true), 1150);
    return () => clearTimeout(t);
  }, [reduce]);
  if (reduce) return null;
  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          className="fixed inset-0 z-[60] grid place-items-center bg-void"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="w-[min(420px,80vw)]">
            <div className="mb-3 font-display text-sm uppercase tracking-[0.4em] text-brand">
              CC<span className="text-bone">DASH</span>
            </div>
            <div className="mb-2 font-mono text-[11px] tracking-[0.25em] text-ash">
              <Typewriter text="INITIALISATION DU CENTRE DE CONTRÔLE…" />
            </div>
            <div className="h-1 w-full overflow-hidden rounded-full bg-grid">
              <div className="h-full animate-boot-bar bg-brand shadow-glow" />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Tiny typewriter that reveals `text` character by character. */
function Typewriter({ text }: { text: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN((v) => (v < text.length ? v + 1 : v)), 22);
    return () => clearInterval(id);
  }, [text]);
  return (
    <span>
      {text.slice(0, n)}
      <span className="text-brand">▍</span>
    </span>
  );
}

/** A blinking telemetry dot. */
export function LiveDot({ on = true }: { on?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`h-2 w-2 rounded-full ${
          on ? "bg-live animate-pulse-dot shadow-[0_0_8px_2px_rgba(155,227,74,0.7)]" : "bg-haze"
        }`}
      />
      <span className={`text-[10px] tracking-[0.25em] ${on ? "text-live" : "text-haze"}`}>
        {on ? "LIVE" : "OFFLINE"}
      </span>
    </span>
  );
}

/** HUD panel with corner ticks + label rail. */
export function Panel({
  label,
  accent = "brand",
  children,
  className = "",
  right,
  index = 0,
}: {
  label?: string;
  accent?: "brand" | "deep";
  children: React.ReactNode;
  className?: string;
  right?: React.ReactNode;
  index?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 10 }}
      animate={reduce ? undefined : { opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.4), duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      whileHover={reduce ? undefined : { y: -3 }}
      className={`hud-frame bg-panel/70 backdrop-blur-sm shadow-panel transition-shadow duration-300 hover:shadow-glow ${className}`}
      style={{ ["--tw-edge" as string]: "#233246" }}
    >
      {(label || right) && (
        <div className="flex items-center justify-between border-b border-grid px-4 py-2">
          {label && (
            <span
              className={`font-display text-[11px] font-600 uppercase tracking-[0.3em] ${
                accent === "brand" ? "text-brand" : "text-deep"
              }`}
            >
              {label}
            </span>
          )}
          {right}
        </div>
      )}
      <div className="p-4">{children}</div>
    </motion.div>
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
  accent = "brand",
  index = 0,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  accent?: "brand" | "deep" | "live" | "alert";
  index?: number;
}) {
  const color = {
    brand: "text-brand",
    deep: "text-deep",
    live: "text-live",
    alert: "text-alert",
  }[accent];
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={reduce ? undefined : { opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4 }}
      whileHover={reduce ? undefined : { y: -3 }}
      className="hud-frame relative overflow-hidden bg-panel/70 px-5 py-4 shadow-panel transition-shadow duration-300 hover:shadow-glow"
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
            accent === "deep"
              ? "linear-gradient(90deg, transparent, #0070AD, transparent)"
              : "linear-gradient(90deg, transparent, #12ABDB, transparent)",
        }}
      />
    </motion.div>
  );
}

/** Thin labelled progress bar (used for leaderboards / shares). */
export function Bar({
  pct,
  accent = "brand",
}: {
  pct: number;
  accent?: "brand" | "deep" | "live";
}) {
  const bg = { brand: "bg-brand", deep: "bg-deep", live: "bg-live" }[accent];
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-grid">
      <div
        className={`h-full ${bg}`}
        style={{ width: `${Math.max(2, Math.min(100, pct))}%` }}
      />
    </div>
  );
}
