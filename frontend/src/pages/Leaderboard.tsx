import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api, type Period, type SortBy } from "../api/client";
import { Bar, Panel, SourceBadge } from "../components/hud";
import { formatCost, formatNum, formatTokens } from "../lib/format";

type Mode = "teams" | "participants" | "locations";

const SORT_LABELS: Record<SortBy, string> = {
  cost: "Coût",
  eval: "Évaluation",
  volume: "Volume",
};

const MODE_LABELS: Record<Mode, string> = {
  teams: "Équipes",
  participants: "Participants",
  locations: "Villes",
};

const PERIOD_LABELS: Record<Period, string> = {
  today: "Aujourd'hui",
  total: "Total",
};

function formatScore(n: number | null): string {
  return n == null ? "—" : `${n}/100`;
}

export default function LeaderboardPage() {
  const [mode, setMode] = useState<Mode>("teams");
  const [sort, setSort] = useState<SortBy>("cost");
  const [period, setPeriod] = useState<Period>("total");
  const teams = useQuery({
    queryKey: ["teams", sort, period],
    queryFn: () => api.teams(sort, period),
    refetchInterval: 30000,
  });
  const parts = useQuery({
    queryKey: ["participants", sort, period],
    queryFn: () => api.participants(sort, period),
    refetchInterval: 30000,
  });
  const locs = useQuery({
    queryKey: ["locations", sort, period],
    queryFn: () => api.locations(sort, period),
    refetchInterval: 30000,
  });
  const cfg = useQuery({ queryKey: ["config"], queryFn: api.config });
  const cur = cfg.data?.currency ?? "€";
  const periodSuffix = period === "today" ? " — aujourd'hui" : "";

  const maxTeamCost = Math.max(1, ...(teams.data ?? []).map((t) => t.cost));
  const maxPartCost = Math.max(1, ...(parts.data ?? []).map((p) => p.cost));
  const maxLocCost = Math.max(1, ...(locs.data ?? []).map((l) => l.cost));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-sm font-600 uppercase tracking-[0.35em] text-ash">
          ▸ Classement général
        </h1>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex border border-edge">
            {(["today", "total"] as Period[]).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-4 py-1.5 font-display text-[11px] font-600 uppercase tracking-[0.2em] transition ${
                  period === p ? "bg-deep text-void" : "text-ash hover:text-bone"
                }`}
              >
                {PERIOD_LABELS[p]}
              </button>
            ))}
          </div>
          <div className="flex border border-edge">
            {(["cost", "eval", "volume"] as SortBy[]).map((s) => (
              <button
                key={s}
                onClick={() => setSort(s)}
                className={`px-4 py-1.5 font-display text-[11px] font-600 uppercase tracking-[0.2em] transition ${
                  sort === s ? "bg-deep text-void" : "text-ash hover:text-bone"
                }`}
              >
                {SORT_LABELS[s]}
              </button>
            ))}
          </div>
          <div className="flex border border-edge">
            {(["teams", "participants", "locations"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-4 py-1.5 font-display text-[11px] font-600 uppercase tracking-[0.2em] transition ${
                  mode === m ? "bg-brand text-void" : "text-ash hover:text-bone"
                }`}
              >
                {MODE_LABELS[m]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {mode === "teams" && (
        <Panel label={`Équipes — classées par ${SORT_LABELS[sort].toLowerCase()}${periodSuffix}`} accent="brand">
          <Table head={["#", "Équipe", "Ville", "Membres", "Sessions", "Tokens", "Volume", "Éval", "Cache", "Coût"]}>
            {(teams.data ?? []).map((t, i) => (
              <Row key={t.team_id} index={i}>
                <Rank n={t.rank} />
                <td className="py-2">
                  <Link
                    to={`/teams/${encodeURIComponent(t.team_id)}`}
                    className="font-display tracking-wide text-bone hover:text-brand"
                  >
                    {t.team_id}
                  </Link>
                </td>
                <Cell className="text-ash">{t.localisation}</Cell>
                <Cell>{t.participant_count}</Cell>
                <Cell>{t.session_count}</Cell>
                <Cell>{formatTokens(t.tokens)}</Cell>
                <Cell>{formatNum(t.volume)}</Cell>
                <Cell className="text-brand">{formatScore(t.eval_score)}</Cell>
                <td className="py-2 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="w-10 text-right font-mono text-[11px] text-deep tnum">
                      {(t.cache_efficiency * 100).toFixed(0)}%
                    </span>
                    <div className="w-16">
                      <Bar pct={t.cache_efficiency * 100} accent="deep" />
                    </div>
                  </div>
                </td>
                <td className="py-2 pr-2">
                  <div className="flex items-center justify-end gap-3">
                    <div className="hidden w-24 sm:block">
                      <Bar pct={(t.cost / maxTeamCost) * 100} accent="brand" />
                    </div>
                    <span className="font-mono font-600 text-brand tnum">
                      {formatCost(t.cost, cur)}
                    </span>
                  </div>
                </td>
              </Row>
            ))}
          </Table>
        </Panel>
      )}

      {mode === "participants" && (
        <Panel label={`Participants — classés par ${SORT_LABELS[sort].toLowerCase()}${periodSuffix}`} accent="deep">
          <Table head={["#", "Participant", "Équipe", "Sessions", "Tokens", "Volume", "Éval", "Coût"]}>
            {(parts.data ?? []).map((p, i) => (
              <Row key={p.user_id} index={i}>
                <Rank n={p.rank} />
                <Cell className="font-display tracking-wide text-bone">
                  {p.display_name}
                  <SourceBadge sources={p.data_sources} />
                </Cell>
                <Cell className="text-ash">{p.team_id}</Cell>
                <Cell>{p.session_count}</Cell>
                <Cell>{formatTokens(p.tokens)}</Cell>
                <Cell>{formatNum(p.volume)}</Cell>
                <Cell className="text-brand">{formatScore(p.score)}</Cell>
                <td className="py-2 pr-2">
                  <div className="flex items-center justify-end gap-3">
                    <div className="hidden w-24 sm:block">
                      <Bar pct={(p.cost / maxPartCost) * 100} accent="deep" />
                    </div>
                    <span className="font-mono font-600 text-deep tnum">
                      {formatCost(p.cost, cur)}
                    </span>
                  </div>
                </td>
              </Row>
            ))}
          </Table>
        </Panel>
      )}

      {mode === "locations" && (
        <Panel label={`Villes — classées par ${SORT_LABELS[sort].toLowerCase()}${periodSuffix}`} accent="brand">
          <Table head={["#", "Ville", "Équipes", "Membres", "Sessions", "Tokens", "Volume", "Éval", "Cache", "Coût"]}>
            {(locs.data ?? []).map((l, i) => (
              <Row key={l.localisation} index={i}>
                <Rank n={l.rank} />
                <Cell className="font-display tracking-wide text-bone">
                  {l.localisation}
                </Cell>
                <Cell className="text-ash">{l.team_count}</Cell>
                <Cell>{l.participant_count}</Cell>
                <Cell>{l.session_count}</Cell>
                <Cell>{formatTokens(l.tokens)}</Cell>
                <Cell>{formatNum(l.volume)}</Cell>
                <Cell className="text-brand">{formatScore(l.eval_score)}</Cell>
                <td className="py-2 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="w-10 text-right font-mono text-[11px] text-deep tnum">
                      {(l.cache_efficiency * 100).toFixed(0)}%
                    </span>
                    <div className="w-16">
                      <Bar pct={l.cache_efficiency * 100} accent="deep" />
                    </div>
                  </div>
                </td>
                <td className="py-2 pr-2">
                  <div className="flex items-center justify-end gap-3">
                    <div className="hidden w-24 sm:block">
                      <Bar pct={(l.cost / maxLocCost) * 100} accent="brand" />
                    </div>
                    <span className="font-mono font-600 text-brand tnum">
                      {formatCost(l.cost, cur)}
                    </span>
                  </div>
                </td>
              </Row>
            ))}
          </Table>
        </Panel>
      )}
    </div>
  );
}

function Table({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <table className="w-full border-collapse">
      <thead>
        <tr className="border-b border-grid text-left">
          {head.map((h, i) => (
            <th
              key={h}
              className={`pb-2 font-display text-[10px] uppercase tracking-[0.2em] text-haze ${
                i >= head.length - 1 ? "text-right" : ""
              }`}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}

function Row({ index, children }: { index: number; children: React.ReactNode }) {
  return (
    <motion.tr
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: Math.min(index * 0.025, 0.4) }}
      className="border-b border-grid/50 text-sm hover:bg-panel-2/60"
    >
      {children}
    </motion.tr>
  );
}

function Cell({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`py-2 font-mono text-bone tnum ${className}`}>{children}</td>;
}

function Rank({ n }: { n: number }) {
  const medal = n === 1 ? "text-brand" : n === 2 ? "text-bone" : n === 3 ? "text-deep" : "text-haze";
  return (
    <td className={`py-2 pr-2 font-display text-base font-700 tnum ${medal}`}>
      {String(n).padStart(2, "0")}
    </td>
  );
}
