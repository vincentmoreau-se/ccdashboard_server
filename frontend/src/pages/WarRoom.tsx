import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api, type LiveSnapshot } from "../api/client";
import { subscribeLive } from "../api/sse";
import { Bar, CountUp, Gauge, LiveDot, Panel } from "../components/hud";
import { formatCost, formatTokens } from "../lib/format";

export default function WarRoom() {
  const [snap, setSnap] = useState<LiveSnapshot | null>(null);
  const [connected, setConnected] = useState(false);

  // SSE is the primary feed; the initial fetch fills the screen instantly.
  const { data: initial } = useQuery({
    queryKey: ["live-initial"],
    queryFn: api.liveSnapshot,
  });

  useEffect(() => {
    if (initial && !snap) setSnap(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  useEffect(() => {
    return subscribeLive(setSnap, setConnected);
  }, []);

  const cur = snap?.currency ?? "€";
  const maxTeamTokens = Math.max(1, ...(snap?.top_teams ?? []).map((t) => t.tokens));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-sm font-600 uppercase tracking-[0.35em] text-ash">
          ▸ Activité temps réel
        </h1>
        <LiveDot on={connected} />
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Gauge
          index={0}
          label="Sessions actives"
          accent="lime"
          value={<CountUp value={snap?.active_sessions ?? 0} />}
        />
        <Gauge
          index={1}
          label="Participants"
          accent="cyan"
          value={<CountUp value={snap?.active_participants ?? 0} />}
        />
        <Gauge
          index={2}
          label="Équipes actives"
          accent="cyan"
          value={<CountUp value={snap?.active_teams ?? 0} />}
        />
        <Gauge
          index={3}
          label="Débit tokens"
          unit="/min"
          accent="amber"
          value={
            snap?.tokens_per_min == null ? (
              <span className="text-haze">···</span>
            ) : (
              <CountUp value={snap.tokens_per_min} />
            )
          }
        />
        <Gauge
          index={4}
          label="Coût horaire"
          unit={`${cur}/h`}
          accent="rose"
          value={
            snap?.cost_per_hour == null ? (
              <span className="text-haze">···</span>
            ) : (
              <CountUp value={snap.cost_per_hour} decimals={2} />
            )
          }
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Panel label="Top équipes — maintenant" accent="amber" className="lg:col-span-2">
          {snap && snap.top_teams.length > 0 ? (
            <div className="space-y-3">
              {snap.top_teams.map((t, i) => (
                <motion.div
                  key={t.team_id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="grid grid-cols-[auto_1fr_auto] items-center gap-3"
                >
                  <span className="w-6 text-right font-display text-sm font-700 text-haze tnum">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <div className="mb-1 flex items-baseline justify-between">
                      <span className="font-display text-sm tracking-wide text-bone">
                        {t.team_id}
                      </span>
                      <span className="font-mono text-xs text-ash tnum">
                        {formatTokens(t.tokens)} tok ▏ {t.active_sessions} sess.
                      </span>
                    </div>
                    <Bar pct={(t.tokens / maxTeamTokens) * 100} accent="amber" />
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <Empty>Aucune équipe active — en attente de télémétrie…</Empty>
          )}
        </Panel>

        <div className="space-y-5">
          <Panel label="Tokens live (fenêtre)" accent="cyan">
            <div className="font-display text-3xl font-700 text-cyan tnum">
              <CountUp value={snap?.live_tokens ?? 0} />
            </div>
            <div className="mt-1 font-mono text-[11px] tracking-widest text-haze">
              {formatCost(snap?.live_cost ?? 0, cur)} engagés
            </div>
          </Panel>

          <Panel label="Modèles en service" accent="amber">
            {snap && snap.models_in_use.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {snap.models_in_use.map((m) => (
                  <span
                    key={m.model}
                    className="border border-edge bg-void/60 px-2.5 py-1 font-mono text-[11px] text-bone"
                  >
                    {m.model}
                    <span className="ml-1.5 text-amber tnum">×{m.count}</span>
                  </span>
                ))}
              </div>
            ) : (
              <Empty>—</Empty>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="py-6 text-center font-mono text-[11px] tracking-widest text-haze">
      {children}
    </div>
  );
}
