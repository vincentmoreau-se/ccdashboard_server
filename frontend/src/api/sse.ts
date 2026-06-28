import type { LiveSnapshot } from "./client";

const BASE = import.meta.env.VITE_API_BASE ?? "";

/**
 * Subscribe to the live SSE stream with auto-reconnect backoff.
 * Auth rides on the session cookie (EventSource can't set headers).
 */
export function subscribeLive(
  onData: (snap: LiveSnapshot) => void,
  onStatus?: (connected: boolean) => void
): () => void {
  let es: EventSource | null = null;
  let closed = false;
  let retry = 1000;

  const connect = () => {
    if (closed) return;
    es = new EventSource(`${BASE}/api/live/stream`, { withCredentials: true });

    es.addEventListener("live_snapshot", (ev) => {
      retry = 1000;
      onStatus?.(true);
      try {
        onData(JSON.parse((ev as MessageEvent).data));
      } catch {
        /* ignore malformed frame */
      }
    });

    es.onerror = () => {
      onStatus?.(false);
      es?.close();
      if (closed) return;
      setTimeout(connect, retry);
      retry = Math.min(retry * 2, 15000);
    };
  };

  connect();
  return () => {
    closed = true;
    es?.close();
  };
}
