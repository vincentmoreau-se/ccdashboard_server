import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { Gauge, Panel } from "../components/hud";
import { formatCost, formatTokens } from "../lib/format";

const DONUT = ["#ffb000", "#36e0e0", "#9be34a", "#ff5d62", "#8595a8", "#c792ea"];

export default function History() {
  const [metric, setMetric] = useState<"cost" | "tokens">("cost");
  const cfg = useQuery({ queryKey: ["config"], queryFn: api.config });
  const cur = cfg.data?.currency ?? "€";
  const opts = { refetchInterval: 30000 };

  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview, ...opts });
  const ts = useQuery({
    queryKey: ["timeseries", metric],
    queryFn: () => api.timeseries("hour", metric),
    ...opts,
  });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models, ...opts });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.providers, ...opts });
  const tools = useQuery({ queryKey: ["tools"], queryFn: api.tools, ...opts });

  const ov = overview.data;

  return (
    <div className="space-y-5">
      <h1 className="font-display text-sm font-600 uppercase tracking-[0.35em] text-ash">
        ▸ Bilan cumulé de l'événement
      </h1>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Gauge index={0} label="Coût total" unit={cur} accent="amber"
          value={<span className="tnum">{(ov?.total_cost ?? 0).toFixed(2)}</span>} />
        <Gauge index={1} label="Tokens totaux" accent="cyan"
          value={formatTokens(ov?.total_tokens ?? 0)} />
        <Gauge index={2} label="Sessions" accent="lime"
          value={<span className="tnum">{ov?.session_count ?? 0}</span>} />
        <Gauge index={3} label="Efficacité cache" unit="%" accent="cyan"
          value={<span className="tnum">{((ov?.cache_efficiency ?? 0) * 100).toFixed(0)}</span>} />
      </div>

      <Panel
        label={`Consommation dans le temps — ${metric === "cost" ? "coût" : "tokens"}`}
        accent="amber"
        right={
          <div className="flex border border-edge">
            {(["cost", "tokens"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMetric(m)}
                className={`px-3 py-1 font-display text-[10px] uppercase tracking-[0.2em] ${
                  metric === m ? "bg-amber text-void" : "text-ash hover:text-bone"
                }`}
              >
                {m === "cost" ? cur : "TOK"}
              </button>
            ))}
          </div>
        }
      >
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={ts.data ?? []} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ffb000" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#ffb000" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="bucket" tick={{ fill: "#5b6878", fontSize: 10, fontFamily: "IBM Plex Mono" }}
                tickFormatter={(v: string) => v.slice(11) || v} stroke="#2a3543" />
              <YAxis tick={{ fill: "#5b6878", fontSize: 10, fontFamily: "IBM Plex Mono" }}
                stroke="#2a3543" width={48} />
              <Tooltip content={<ChartTip metric={metric} cur={cur} />} />
              <Area type="monotone" dataKey="value" stroke="#ffb000" strokeWidth={2}
                fill="url(#g)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel label="Répartition par modèle" accent="cyan">
          <div className="flex items-center gap-4">
            <div className="h-52 w-52 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={models.data ?? []} dataKey="tokens" nameKey="model"
                    cx="50%" cy="50%" innerRadius={48} outerRadius={80} paddingAngle={2}
                    stroke="#07090d" strokeWidth={2}>
                    {(models.data ?? []).map((_, i) => (
                      <Cell key={i} fill={DONUT[i % DONUT.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<DonutTip cur={cur} />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="min-w-0 flex-1 space-y-1.5">
              {(models.data ?? []).slice(0, 6).map((m, i) => (
                <div key={m.model} className="flex items-center justify-between gap-2 text-sm">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="h-2.5 w-2.5 shrink-0" style={{ background: DONUT[i % DONUT.length] }} />
                    <span className="truncate font-mono text-bone">{m.model}</span>
                  </span>
                  <span className="shrink-0 font-mono text-xs text-ash tnum">
                    {formatTokens(m.tokens)}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-3 border-t border-grid pt-3">
            {(providers.data ?? []).map((p) => (
              <span key={p.provider} className="font-mono text-[11px] text-haze">
                <span className="text-cyan">{p.provider}</span> ▏ {formatCost(p.cost, cur)} ▏{" "}
                {p.session_count} sess.
              </span>
            ))}
          </div>
        </Panel>

        <Panel label="Outils les plus utilisés" accent="amber">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={(tools.data ?? []).slice(0, 10)} layout="vertical"
                margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
                <XAxis type="number" tick={{ fill: "#5b6878", fontSize: 10, fontFamily: "IBM Plex Mono" }}
                  stroke="#2a3543" />
                <YAxis type="category" dataKey="tool" width={90}
                  tick={{ fill: "#e6edf3", fontSize: 11, fontFamily: "IBM Plex Mono" }} stroke="#2a3543" />
                <Tooltip cursor={{ fill: "#11161f" }} content={<ToolTip />} />
                <Bar dataKey="count" fill="#36e0e0" radius={[0, 2, 2, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function box(children: React.ReactNode) {
  return (
    <div className="border border-edge bg-void/90 px-3 py-2 font-mono text-[11px] text-bone shadow-glow">
      {children}
    </div>
  );
}

function ChartTip({ active, payload, label, metric, cur }: any) {
  if (!active || !payload?.length) return null;
  const v = payload[0].value;
  return box(
    <>
      <div className="text-haze">{label}</div>
      <div className="text-amber tnum">
        {metric === "cost" ? formatCost(v, cur) : formatTokens(v) + " tokens"}
      </div>
    </>
  );
}

function DonutTip({ active, payload, cur }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return box(
    <>
      <div className="text-bone">{d.model}</div>
      <div className="text-cyan tnum">{formatTokens(d.tokens)} tok ▏ {formatCost(d.cost, cur)}</div>
    </>
  );
}

function ToolTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return box(<span className="text-cyan">{d.tool}: <span className="tnum">{d.count}</span></span>);
}
