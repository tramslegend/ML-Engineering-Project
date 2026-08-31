"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { Check, X, TriangleAlert, ChevronDown, Search, PlayCircle } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import Card from "@/components/Card";
import Badge, { FLAG_STATUS_TONE } from "@/components/Badge";
import EmptyState from "@/components/EmptyState";
import Skeleton from "@/components/Skeleton";
import { Flag, apiFetch } from "@/lib/api";

const FILTERS: { key: string; label: string }[] = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "accepted", label: "Accepted" },
  { key: "escalated", label: "Escalated" },
  { key: "rejected", label: "Rejected" },
];

export default function ScreeningPage() {
  const [flags, setFlags] = useState<Flag[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [confirmEscalate, setConfirmEscalate] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const data = await apiFetch<Flag[]>("/flags");
      setFlags(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load flags");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function runScreening() {
    setLoading(true);
    setError(null);
    try {
      await apiFetch<Flag[]>("/flags/screen", { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Screening run failed");
    } finally {
      setLoading(false);
    }
  }

  async function decide(id: string, decision: string) {
    try {
      await apiFetch<Flag>(`/flags/${id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, note: note[id] || undefined }),
      });
      setConfirmEscalate(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    }
  }

  const filtered = useMemo(() => {
    if (!flags) return [];
    return flags
      .filter((f) => filter === "all" || f.status === filter)
      .filter(
        (f) =>
          !search ||
          f.rule_triggered.toLowerCase().includes(search.toLowerCase()) ||
          f.transaction_ref.toLowerCase().includes(search.toLowerCase())
      );
  }, [flags, filter, search]);

  return (
    <AuthShell
      eyebrow="AML / APU-PPT"
      title="Screening Queue"
      action={
        <button
          onClick={runScreening}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg bg-bpr-navy px-4 py-2.5 text-[13px] font-medium text-bpr-parchment transition-colors hover:bg-bpr-navyLight disabled:opacity-50"
        >
          <PlayCircle className="h-4 w-4" strokeWidth={1.75} />
          {loading ? "Running..." : "Run screening"}
        </button>
      }
    >
      {error && <p className="mb-4 rounded-lg bg-bpr-rose/10 p-3 text-sm text-bpr-rose">{error}</p>}

      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="flex gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-full px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
                filter === f.key ? "bg-bpr-navy text-bpr-parchment" : "bg-bpr-card text-bpr-ink2/70 ring-1 ring-inset ring-bpr-hairline hover:bg-bpr-parchmentDark"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-bpr-ink2/40" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search rule or transaction..."
            className="w-64 rounded-lg border border-bpr-hairline bg-bpr-card py-1.5 pl-8 pr-3 text-[12.5px] outline-none focus:border-bpr-brass/50"
          />
        </div>
      </div>

      {!flags && (
        <div className="space-y-2">
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      )}

      {flags && filtered.length === 0 && <EmptyState title="No flags match" hint="Try a different filter or run screening on new transactions." />}

      {flags && filtered.length > 0 && (
        <Card padded={false} className="overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-bpr-parchmentDark/60 text-[11px] uppercase tracking-wide text-bpr-ink2/55">
              <tr>
                <th className="w-8 px-4 py-2.5" />
                <th className="px-2 py-2.5">Rule(s)</th>
                <th className="px-2 py-2.5">Transaction</th>
                <th className="px-2 py-2.5">Status</th>
                <th className="px-2 py-2.5">Flagged</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((flag) => {
                const isOpen = expanded === flag.id;
                return (
                  <Fragment key={flag.id}>
                    <tr
                      onClick={() => setExpanded(isOpen ? null : flag.id)}
                      className="cursor-pointer border-t border-bpr-hairline transition-colors hover:bg-bpr-parchmentDark/40"
                    >
                      <td className="px-4 py-3">
                        <ChevronDown className={`h-4 w-4 text-bpr-ink2/40 transition-transform ${isOpen ? "rotate-180" : ""}`} strokeWidth={1.75} />
                      </td>
                      <td className="px-2 py-3 font-medium text-bpr-navy">{flag.rule_triggered}</td>
                      <td className="px-2 py-3 font-mono text-[11.5px] text-bpr-ink2/55">{flag.transaction_ref}</td>
                      <td className="px-2 py-3">
                        <Badge tone={FLAG_STATUS_TONE[flag.status]}>{flag.status}</Badge>
                      </td>
                      <td className="px-2 py-3 text-[12px] text-bpr-ink2/55">{new Date(flag.created_at).toLocaleDateString()}</td>
                    </tr>
                    {isOpen && (
                      <tr className="border-t border-bpr-hairline bg-bpr-parchmentDark/30">
                        <td colSpan={5} className="px-4 py-4">
                          <div className="grid grid-cols-2 gap-6">
                            <div>
                              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/50">Agent rationale</p>
                              <p className="text-[13px] leading-relaxed text-bpr-navy">{flag.agent_rationale || "—"}</p>
                              <p className="mb-1 mt-3 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/50">Reviewer check</p>
                              <p className="text-[13px] text-bpr-ink2/70">{flag.reviewer_verdict || "—"}</p>
                            </div>
                            {flag.status === "open" ? (
                              <div onClick={(e) => e.stopPropagation()}>
                                <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/50">Your decision</p>
                                <input
                                  placeholder="Decision note (optional)"
                                  value={note[flag.id] || ""}
                                  onChange={(e) => setNote({ ...note, [flag.id]: e.target.value })}
                                  className="mb-3 w-full rounded-lg border border-bpr-hairline bg-bpr-card px-3 py-2 text-[12.5px] outline-none focus:border-bpr-brass/50"
                                />
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => decide(flag.id, "accepted")}
                                    className="flex items-center gap-1.5 rounded-lg bg-bpr-teal px-3 py-1.5 text-[12.5px] font-medium text-white hover:opacity-90"
                                  >
                                    <Check className="h-3.5 w-3.5" strokeWidth={2} /> Accept
                                  </button>
                                  <button
                                    onClick={() => decide(flag.id, "rejected")}
                                    className="flex items-center gap-1.5 rounded-lg bg-bpr-ink2/15 px-3 py-1.5 text-[12.5px] font-medium text-bpr-ink2 hover:bg-bpr-ink2/25"
                                  >
                                    <X className="h-3.5 w-3.5" strokeWidth={2} /> Reject
                                  </button>
                                  {confirmEscalate === flag.id ? (
                                    <button
                                      onClick={() => decide(flag.id, "escalated")}
                                      className="flex items-center gap-1.5 rounded-lg bg-bpr-plum px-3 py-1.5 text-[12.5px] font-medium text-white"
                                    >
                                      Confirm escalate?
                                    </button>
                                  ) : (
                                    <button
                                      onClick={() => setConfirmEscalate(flag.id)}
                                      className="flex items-center gap-1.5 rounded-lg bg-bpr-plum/10 px-3 py-1.5 text-[12.5px] font-medium text-bpr-plum hover:bg-bpr-plum/20"
                                    >
                                      <TriangleAlert className="h-3.5 w-3.5" strokeWidth={2} /> Escalate
                                    </button>
                                  )}
                                </div>
                              </div>
                            ) : (
                              <div>
                                <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/50">Decision</p>
                                <p className="text-[13px] text-bpr-navy">
                                  Marked <span className="font-medium">{flag.status}</span>
                                  {flag.decided_at && ` on ${new Date(flag.decided_at).toLocaleString()}`}
                                </p>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </AuthShell>
  );
}
