// Same-origin in dev (Vite proxies /api -> backend) so the session cookie flows
// automatically. Override with VITE_API_BASE for a split deployment.
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (res.status === 401) throw new ApiError(401, "unauthorized");
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const api = {
  me: () => req<{ authenticated: boolean }>("/api/me"),
  login: (password: string) =>
    req<{ status: string }>("/api/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  logout: () => req<{ status: string }>("/api/logout", { method: "POST" }),
  config: () => req<AppConfig>("/api/config"),
  overview: () => req<Overview>("/api/overview"),
  timeseries: (bucket: "hour" | "day", metric: "cost" | "tokens") =>
    req<TimeBucket[]>(`/api/timeseries?bucket=${bucket}&metric=${metric}`),
  teams: (sort: SortBy = "cost") =>
    req<TeamRow[]>(`/api/leaderboard/teams?sort=${sort}`),
  participants: (sort: SortBy = "cost") =>
    req<ParticipantRow[]>(`/api/leaderboard/participants?sort=${sort}`),
  locations: (sort: SortBy = "cost") =>
    req<LocationRow[]>(`/api/leaderboard/locations?sort=${sort}`),
  team: (id: string) => req<TeamDetail>(`/api/teams/${encodeURIComponent(id)}`),
  models: () => req<ModelRow[]>("/api/models"),
  providers: () => req<ProviderRow[]>("/api/providers"),
  tools: () => req<ToolRow[]>("/api/tools"),
  sessions: (active = false, limit = 100) =>
    req<SessionRow[]>(`/api/sessions?active=${active}&limit=${limit}`),
  liveSnapshot: () => req<LiveSnapshot>("/api/live/snapshot"),
};

export interface AppConfig {
  currency: string;
  event_name: string;
  live_window_seconds: number;
  snapshot_interval_seconds: number;
}

export interface Overview {
  session_count: number;
  participant_count: number;
  team_count: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cache_efficiency: number;
  total_cost: number;
  cost_known: boolean;
}

export interface TimeBucket {
  bucket: string;
  session_count: number;
  tokens: number;
  cost: number;
  value: number;
}

export type SortBy = "cost" | "eval" | "volume";

export interface TeamRow {
  rank: number;
  team_id: string;
  localisation: string;
  participant_count: number;
  session_count: number;
  tokens: number;
  cost: number;
  volume: number;
  eval_score: number | null;
  cache_efficiency: number;
}

export interface LocationRow {
  rank: number;
  localisation: string;
  team_count: number;
  participant_count: number;
  session_count: number;
  tokens: number;
  cost: number;
  volume: number;
  eval_score: number | null;
  cache_efficiency: number;
}

export interface ParticipantRow {
  rank: number;
  user_id: string;
  display_name: string;
  team_id: string;
  session_count: number;
  tokens: number;
  cost: number;
  volume: number;
  score: number | null;
}

export interface ModelRow {
  model: string;
  provider: string;
  session_count: number;
  tokens: number;
  cost: number;
}

export interface ProviderRow {
  provider: string;
  session_count: number;
  tokens: number;
  cost: number;
}

export interface ToolRow {
  tool: string;
  count: number;
}

export interface SessionRow {
  session_id: string;
  user_id: string;
  team_id: string | null;
  project: string;
  ai_title: string | null;
  models: string[];
  provider: string;
  is_active: boolean;
  message_count: number;
  duration_seconds: number | null;
  tokens: number;
  cost: number;
  started_at: string | null;
  ended_at: string | null;
}

export interface LiveSnapshot {
  ts: string;
  active_sessions: number;
  active_participants: number;
  active_teams: number;
  live_tokens: number;
  live_cost: number;
  tokens_per_min: number | null;
  cost_per_hour: number | null;
  top_teams: { team_id: string; active_sessions: number; tokens: number }[];
  models_in_use: { model: string; count: number }[];
  currency: string;
}

export interface TeamDetail {
  team_id: string;
  localisation: string;
  participants: string[];
  session_count: number;
  models: { model: string; session_count: number }[];
  sessions: SessionRow[];
}
