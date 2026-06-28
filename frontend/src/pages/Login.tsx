import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "../api/client";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.login(password);
      // Set the auth cache directly so the route guard doesn't bounce back to
      // /login during a background refetch.
      qc.setQueryData(["me"], { authenticated: true });
      navigate("/");
    } catch {
      setError("ACCÈS REFUSÉ — code invalide");
      setBusy(false);
    }
  };

  return (
    <div className="relative z-10 grid min-h-screen place-items-center px-4">
      <motion.form
        onSubmit={submit}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="hud-frame w-full max-w-md bg-panel/80 p-8 shadow-panel"
      >
        <div className="mb-1 font-display text-2xl font-700 tracking-[0.18em] text-bone">
          CC<span className="text-brand">DASH</span>{" "}
          <span className="text-haze">▏</span> ACCÈS
        </div>
        <p className="mb-7 font-mono text-[11px] uppercase tracking-[0.28em] text-haze">
          centre de contrôle — authentification requise
        </p>

        <label className="mb-2 block font-display text-[11px] uppercase tracking-[0.28em] text-deep">
          Code d'accès
        </label>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-void/80 px-4 py-3 font-mono text-bone outline-none ring-1 ring-edge transition focus:ring-brand"
          placeholder="••••••••••"
        />

        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-3 font-mono text-[11px] tracking-[0.2em] text-alert"
          >
            ⚠ {error}
          </motion.div>
        )}

        <button
          type="submit"
          disabled={busy || !password}
          className="mt-7 w-full bg-brand px-4 py-3 font-display text-sm font-700 uppercase tracking-[0.25em] text-void transition hover:bg-brand/90 disabled:opacity-40"
        >
          {busy ? "VÉRIFICATION…" : "ENTRER ►"}
        </button>
      </motion.form>
    </div>
  );
}
