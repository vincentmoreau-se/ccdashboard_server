export function formatTokens(n: number): string {
  if (n >= 1_000_000_000) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1_000_000) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1e3).toFixed(1) + "k";
  return String(n);
}

export function formatCost(n: number | null | undefined, currency = "€"): string {
  if (n == null) return "n/a";
  return `${n.toFixed(2)} ${currency}`;
}

export function formatNum(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("fr-FR");
}

export function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h) return `${h}h${String(m).padStart(2, "0")}`;
  if (m) return `${m}m${String(s).padStart(2, "0")}`;
  return `${s}s`;
}

export function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}
