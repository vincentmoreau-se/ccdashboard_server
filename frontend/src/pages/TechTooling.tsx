import { useQuery } from "@tanstack/react-query";
import {
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

const PALETTE = ["#12ABDB", "#0070AD", "#00BFB3", "#7B61FF", "#4FC3F7", "#1D4F91", "#9be34a", "#ff5d62"];
const DEEP = "#0070AD";
const BRAND = "#12ABDB";

// Defensive: keep "top N" honest even if the backend changes its ordering.
const byCount = (a: { count: number }, b: { count: number }) => b.count - a.count;

export default function TechTooling() {
  const opts = { refetchInterval: 30000 };
  const tech = useQuery({ queryKey: ["technologies"], queryFn: api.technologies, ...opts });
  const tooling = useQuery({ queryKey: ["tooling"], queryFn: api.tooling, ...opts });

  if (tech.isLoading || tooling.isLoading)
    return (
      <div className="grid h-64 place-items-center font-display tracking-[0.3em] text-ash">
        CHARGEMENT…
      </div>
    );

  if (tech.isError || tooling.isError)
    return (
      <div className="grid h-64 place-items-center font-mono text-alert">
        Erreur de chargement des données
      </div>
    );

  const td = tech.data!;
  const tl = tooling.data!;

  const langs = [...td.languages].sort(byCount).slice(0, 8);
  const frameworks = [...td.frameworks].sort(byCount).slice(0, 10);
  const builtin = [...tl.builtin].sort(byCount).slice(0, 10);
  const userTools = [...tl.user].sort(byCount).slice(0, 10);

  return (
    <div className="space-y-5">
      <h1 className="font-display text-sm font-600 uppercase tracking-[0.35em] text-ash">
        ▸ Technologies &amp; outils
      </h1>

      {/* KPI Gauges */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Gauge
          index={0}
          label="Langages"
          accent="brand"
          value={<span className="tnum">{td.languages.length}</span>}
        />
        <Gauge
          index={1}
          label="Frameworks"
          accent="deep"
          value={<span className="tnum">{td.frameworks.length}</span>}
        />
        <Gauge
          index={2}
          label="Outils intégrés"
          accent="live"
          value={<span className="tnum">{tl.builtin.length}</span>}
        />
        <Gauge
          index={3}
          label="Outils utilisateur"
          accent="brand"
          value={<span className="tnum">{tl.user.length}</span>}
        />
        <Gauge
          index={4}
          label="Skills"
          accent="deep"
          value={<span className="tnum">{tl.skills.length}</span>}
        />
        <Gauge
          index={5}
          label="Serveurs MCP"
          accent="live"
          value={<span className="tnum">{tl.mcp_servers.length}</span>}
        />
      </div>

      {/* Languages donut + Frameworks horizontal bar */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel label="Langages — mix" accent="deep">
          {langs.length === 0 ? (
            <Empty />
          ) : (
            <div className="flex items-center gap-4">
              <div className="h-52 w-52 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={langs}
                      dataKey="count"
                      nameKey="language"
                      cx="50%"
                      cy="50%"
                      innerRadius={48}
                      outerRadius={80}
                      paddingAngle={2}
                      stroke="#04070d"
                      strokeWidth={2}
                      isAnimationActive={false}
                    >
                      {langs.map((_, i) => (
                        <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<LangTip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="min-w-0 flex-1 space-y-1.5">
                {langs.map((lang, i) => (
                  <div
                    key={lang.language}
                    className="flex items-center justify-between gap-2 text-sm"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 shrink-0"
                        style={{ background: PALETTE[i % PALETTE.length] }}
                      />
                      <span className="truncate font-mono text-bone">{lang.language}</span>
                    </span>
                    <span className="shrink-0 font-mono text-xs text-ash tnum">{lang.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>

        <Panel label="Frameworks — top 10" accent="brand">
          {frameworks.length === 0 ? (
            <Empty />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={frameworks}
                  layout="vertical"
                  margin={{ top: 0, right: 12, left: 8, bottom: 0 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fill: "#5b6878", fontSize: 10, fontFamily: "IBM Plex Mono" }}
                    stroke="#233246"
                  />
                  <YAxis
                    type="category"
                    dataKey="framework"
                    width={100}
                    tick={{ fill: "#e6edf3", fontSize: 11, fontFamily: "IBM Plex Mono" }}
                    stroke="#233246"
                  />
                  <Tooltip cursor={{ fill: "#0f1722" }} content={<FrameworkTip />} />
                  <Bar
                    dataKey="count"
                    fill="#12ABDB"
                    radius={[0, 2, 2, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      {/* Built-in tools vs User tools — two DISTINCT side-by-side visualizations */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel label="Outils intégrés — top 10" accent="deep">
          {builtin.length === 0 ? (
            <Empty />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={builtin}
                  layout="vertical"
                  margin={{ top: 0, right: 12, left: 8, bottom: 0 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fill: "#5b6878", fontSize: 10, fontFamily: "IBM Plex Mono" }}
                    stroke="#233246"
                  />
                  <YAxis
                    type="category"
                    dataKey="tool"
                    width={90}
                    tick={{ fill: "#e6edf3", fontSize: 11, fontFamily: "IBM Plex Mono" }}
                    stroke="#233246"
                  />
                  <Tooltip cursor={{ fill: "#0f1722" }} content={<ToolBarTip color={DEEP} />} />
                  <Bar
                    dataKey="count"
                    fill={DEEP}
                    radius={[0, 2, 2, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel label="Outils utilisateur — top 10" accent="brand">
          {userTools.length === 0 ? (
            <Empty />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={userTools}
                  layout="vertical"
                  margin={{ top: 0, right: 12, left: 8, bottom: 0 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fill: "#5b6878", fontSize: 10, fontFamily: "IBM Plex Mono" }}
                    stroke="#233246"
                  />
                  <YAxis
                    type="category"
                    dataKey="tool"
                    width={90}
                    tick={{ fill: "#e6edf3", fontSize: 11, fontFamily: "IBM Plex Mono" }}
                    stroke="#233246"
                  />
                  <Tooltip cursor={{ fill: "#0f1722" }} content={<ToolBarTip color={BRAND} />} />
                  <Bar
                    dataKey="count"
                    fill={BRAND}
                    radius={[0, 2, 2, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      {/* Skills / MCP Servers / Subagents / Slash commands */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <MiniChart label="Skills" data={tl.skills} accent="deep" />
        <MiniChart label="Serveurs MCP" data={tl.mcp_servers} accent="brand" />
        <MiniChart label="Sous-agents" data={tl.subagents} accent="deep" />
        <MiniChart label="Slash commands" data={tl.slash_commands} accent="brand" />
      </div>
    </div>
  );
}

/* ─── Sub-components ──────────────────────────────────────────────── */

function Empty() {
  return (
    <div className="flex h-20 items-center justify-center font-mono text-xs text-haze">
      Aucune donnée
    </div>
  );
}

function MiniChart({
  label,
  data,
  accent,
}: {
  label: string;
  data: { tool: string; count: number }[];
  accent: "brand" | "deep";
}) {
  // Bar color matches the panel accent so header and bars stay consistent.
  const barColor = accent === "deep" ? DEEP : BRAND;
  return (
    <Panel label={label} accent={accent}>
      {data.length === 0 ? (
        <Empty />
      ) : (
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={[...data].sort(byCount).slice(0, 8)}
              layout="vertical"
              margin={{ top: 0, right: 8, left: 4, bottom: 0 }}
            >
              <XAxis
                type="number"
                tick={{ fill: "#5b6878", fontSize: 9, fontFamily: "IBM Plex Mono" }}
                stroke="#233246"
              />
              <YAxis
                type="category"
                dataKey="tool"
                width={80}
                tick={{ fill: "#e6edf3", fontSize: 10, fontFamily: "IBM Plex Mono" }}
                stroke="#233246"
              />
              <Tooltip cursor={{ fill: "#0f1722" }} content={<ToolBarTip color={barColor} />} />
              <Bar dataKey="count" fill={barColor} radius={[0, 2, 2, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

/* ─── Tooltip helpers (same box pattern as History.tsx) ───────────── */

function box(children: React.ReactNode) {
  return (
    <div className="border border-edge bg-void/90 px-3 py-2 font-mono text-[11px] text-bone shadow-glow">
      {children}
    </div>
  );
}

function LangTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return box(
    <span className="text-deep">
      {d.language}: <span className="tnum">{d.count}</span>
    </span>,
  );
}

function FrameworkTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return box(
    <span className="text-brand">
      {d.framework}: <span className="tnum">{d.count}</span>
    </span>,
  );
}

function ToolBarTip({ active, payload, color }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return box(
    <span style={{ color: color ?? "#0070AD" }}>
      {d.tool}: <span className="tnum">{d.count}</span>
    </span>,
  );
}
