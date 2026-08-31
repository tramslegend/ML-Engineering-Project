"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Stamp } from "lucide-react";
import { login, saveSession } from "@/lib/api";

const DEMO_ACCOUNTS = [
  { id: "loan.officer@bpr.demo", label: "Loan Officer — Budi Santoso" },
  { id: "compliance.officer@bpr.demo", label: "Compliance Officer — Siti Rahayu" },
  { id: "auditor@bpr.demo", label: "Auditor — Agus Wijaya" },
];

export default function LoginPage() {
  const router = useRouter();
  const [authId, setAuthId] = useState(DEMO_ACCOUNTS[1].id);
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const session = await login(authId, password);
      saveSession(session);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-bpr-ink">
      <div className="pointer-events-none absolute inset-0 bg-grain" />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-bpr-brass/10 blur-3xl" />

      <form onSubmit={handleSubmit} className="animate-rise relative w-full max-w-sm rounded-2xl border border-white/10 bg-bpr-navy/60 p-8 shadow-2xl backdrop-blur">
        <div className="mb-6 flex items-center gap-2.5">
          <div className="rounded-lg bg-bpr-brass/15 p-2">
            <Stamp className="h-5 w-5 text-bpr-brassLight" strokeWidth={1.75} />
          </div>
          <div>
            <h1 className="font-display text-[19px] leading-tight text-bpr-parchment">BPR Compliance Copilot</h1>
            <p className="text-[11.5px] text-bpr-parchment/50">AML screening, reporting &amp; audit trail</p>
          </div>
        </div>

        <label className="mb-1.5 block text-[12px] font-medium text-bpr-parchment/70">Account</label>
        <select
          value={authId}
          onChange={(e) => setAuthId(e.target.value)}
          className="mb-4 w-full rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2.5 text-[13.5px] text-bpr-parchment outline-none focus:border-bpr-brass/60"
        >
          {DEMO_ACCOUNTS.map((a) => (
            <option key={a.id} value={a.id} className="bg-bpr-navy">
              {a.label}
            </option>
          ))}
        </select>

        <label className="mb-1.5 block text-[12px] font-medium text-bpr-parchment/70">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-5 w-full rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2.5 text-[13.5px] text-bpr-parchment outline-none focus:border-bpr-brass/60"
        />

        {error && <p className="mb-4 rounded-lg bg-bpr-rose/15 px-3 py-2 text-[12.5px] text-rose-200">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-bpr-brass px-4 py-2.5 text-[13.5px] font-medium text-bpr-ink transition-colors hover:bg-bpr-brassLight disabled:opacity-50"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>

        <p className="mt-5 text-center text-[11px] text-bpr-parchment/35">Portfolio demo — synthetic data only</p>
      </form>
    </div>
  );
}
