import { Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api/client";
import { DeckBackground } from "./components/hud";
import Login from "./pages/Login";
import WarRoom from "./pages/WarRoom";
import LeaderboardPage from "./pages/Leaderboard";
import History from "./pages/History";
import TeamDetail from "./pages/TeamDetail";
import TechTooling from "./pages/TechTooling";

function useAuth() {
  return useQuery({ queryKey: ["me"], queryFn: api.me });
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useAuth();
  if (isLoading)
    return (
      <div className="grid h-screen place-items-center font-display tracking-[0.3em] text-ash">
        INITIALISATION…
      </div>
    );
  if (!data?.authenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

const NAV = [
  { to: "/", label: "FLIGHT DECK", end: true },
  { to: "/leaderboard", label: "CLASSEMENT" },
  { to: "/history", label: "HISTORIQUE" },
  { to: "/tech", label: "TECHNOLOGIES" },
];

function Shell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: config } = useQuery({ queryKey: ["config"], queryFn: api.config });

  const logout = async () => {
    await api.logout();
    qc.clear();
    navigate("/login");
  };

  return (
    <div className="relative z-10 mx-auto flex min-h-screen max-w-[1500px] flex-col px-5 py-5">
      <header className="mb-5 flex items-center justify-between border-b border-grid pb-4">
        <div className="flex items-baseline gap-4">
          <span className="font-display text-xl font-700 tracking-[0.2em] text-bone">
            CC<span className="text-amber">DASH</span>
          </span>
          <span className="hidden font-mono text-[11px] uppercase tracking-[0.3em] text-haze sm:inline">
            ▏ {config?.event_name ?? "Hackathon"} ▏ centre de contrôle
          </span>
        </div>
        <nav className="flex items-center gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `px-3 py-1.5 font-display text-[11px] font-600 tracking-[0.2em] transition ${
                  isActive
                    ? "bg-amber/10 text-amber shadow-glow"
                    : "text-ash hover:text-bone"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
          <button
            onClick={logout}
            className="ml-2 px-3 py-1.5 font-display text-[11px] font-600 tracking-[0.2em] text-haze hover:text-rose"
          >
            DÉCONNEXION
          </button>
        </nav>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="mt-6 border-t border-grid pt-3 font-mono text-[10px] tracking-[0.25em] text-haze">
        CCDASH SERVER ▏ TÉLÉMÉTRIE CLAUDE CODE ▏ FENÊTRE LIVE{" "}
        {config?.live_window_seconds ?? "—"}s
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <>
      <DeckBackground />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <Shell>
                <Routes>
                  <Route path="/" element={<WarRoom />} />
                  <Route path="/leaderboard" element={<LeaderboardPage />} />
                  <Route path="/history" element={<History />} />
                  <Route path="/tech" element={<TechTooling />} />
                  <Route path="/teams/:teamId" element={<TeamDetail />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Shell>
            </RequireAuth>
          }
        />
      </Routes>
    </>
  );
}
