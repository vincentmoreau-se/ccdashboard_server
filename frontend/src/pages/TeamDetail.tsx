import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Panel } from "../components/hud";
import { formatCost, formatDuration, formatTokens, formatTime } from "../lib/format";

export default function TeamDetail() {
  const { teamId = "" } = useParams();
  const cfg = useQuery({ queryKey: ["config"], queryFn: api.config });
  const cur = cfg.data?.currency ?? "€";
  const { data, isLoading } = useQuery({
    queryKey: ["team", teamId],
    queryFn: () => api.team(teamId),
    refetchInterval: 30000,
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Link to="/leaderboard" className="font-mono text-xs text-haze hover:text-brand">
          ◄ CLASSEMENT
        </Link>
        <h1 className="font-display text-lg font-700 tracking-[0.15em] text-bone">
          {teamId}
        </h1>
        {data && (
          <span className="font-mono text-[11px] tracking-widest text-deep">
            ▏ {data.localisation}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="font-mono text-ash">Chargement…</div>
      ) : !data ? null : (
        <>
          <div className="grid gap-5 lg:grid-cols-3">
            <Panel label="Membres" accent="deep">
              <div className="flex flex-wrap gap-2">
                {data.participants.map((p) => (
                  <span key={p} className="border border-edge bg-void/60 px-2.5 py-1 font-mono text-[11px] text-bone">
                    {p}
                  </span>
                ))}
              </div>
            </Panel>
            <Panel label="Modèles utilisés" accent="brand">
              <div className="flex flex-wrap gap-2">
                {data.models.map((m) => (
                  <span key={m.model} className="border border-edge bg-void/60 px-2.5 py-1 font-mono text-[11px] text-bone">
                    {m.model} <span className="text-brand tnum">×{m.session_count}</span>
                  </span>
                ))}
              </div>
            </Panel>
            <Panel label="Volume" accent="deep">
              <div className="font-display text-3xl font-700 text-deep tnum">
                {data.session_count}
              </div>
              <div className="font-mono text-[11px] tracking-widest text-haze">sessions</div>
            </Panel>
          </div>

          <Panel label="Sessions" accent="brand">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-grid text-left">
                  {["Projet", "Participant", "Modèle", "Durée", "Msgs", "Tokens", "Coût", "Début"].map((h, i) => (
                    <th key={h} className={`pb-2 font-display text-[10px] uppercase tracking-[0.2em] text-haze ${i >= 6 ? "text-right" : ""}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.sessions.map((s) => (
                  <tr key={s.session_id} className="border-b border-grid/50 hover:bg-panel-2/60">
                    <td className="py-2 font-mono text-bone">
                      {s.is_active && <span className="mr-1.5 text-live">●</span>}
                      {s.project}
                    </td>
                    <td className="py-2 font-mono text-ash">{s.user_id}</td>
                    <td className="py-2 font-mono text-xs text-ash">{s.models.join(", ") || "—"}</td>
                    <td className="py-2 font-mono text-ash tnum">{formatDuration(s.duration_seconds)}</td>
                    <td className="py-2 font-mono text-ash tnum">{s.message_count}</td>
                    <td className="py-2 text-right font-mono text-deep tnum">{formatTokens(s.tokens)}</td>
                    <td className="py-2 text-right font-mono text-brand tnum">{formatCost(s.cost, cur)}</td>
                    <td className="py-2 text-right font-mono text-haze tnum">{formatTime(s.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        </>
      )}
    </div>
  );
}
