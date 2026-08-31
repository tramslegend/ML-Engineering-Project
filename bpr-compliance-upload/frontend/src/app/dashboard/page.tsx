"use client";

import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { ShieldAlert, AlarmClockPlus, FileClock, Inbox, ScrollText, Gavel } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import Card from "@/components/Card";
import StatCard from "@/components/StatCard";
import Badge, { FLAG_STATUS_TONE } from "@/components/Badge";
import EmptyState from "@/components/EmptyState";
import Skeleton from "@/components/Skeleton";
import { AuditEntry, DashboardSummary, Flag, Session, apiFetch, getDashboardSummary, getSession } from "@/lib/api";

const CHART_COLORS: Record<string, string> = {
  open: "#B8892B",
  accepted: "#1F6B57",
  rejected: "#9AA3B2",
  escalated: "#5C3F80",
};

function LedgerFeed({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) return <EmptyState title="No activity yet" hint="Actions taken across the copilot will appear here." />;
  return (
    <ul className="space-y-0">
      {entries.map((e, idx) => (
        <li key={e.id} className={`flex items-start gap-3 py-2.5 text-[13px] ${idx !== entries.length - 1 ? "border-b border-bpr-hairline" : ""}`}>
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-bpr-brass" />
          <div className="min-w-0 flex-1">
            <p className="text-bpr-navy">
              <span className="font-medium">{e.actor}</span>{" "}
              <span className="text-bpr-ink2/70">{e.action.replace(/_/g, " ")}</span>
            </p>
            {e.rationale && <p className="mt-0.5 truncate text-bpr-ink2/50">{e.rationale}</p>}
          </div>
          <span className="shrink-0 whitespace-nowrap text-[11px] text-bpr-ink2/40">
            {new Date(e.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function DashboardPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [attention, setAttention] = useState<Flag[]>([]);
  const [auditorFeed, setAuditorFeed] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSession(getSession());
  }, []);

  useEffect(() => {
    if (!session) return;
    (async () => {
      try {
        const s = await getDashboardSummary();
        setSummary(s);
        if (session.role === "compliance_officer") {
          const open = await apiFetch<Flag[]>("/flags?status_filter=open");
          setAttention(open.slice(0, 5));
        }
        if (session.role === "auditor") {
          const recent = await apiFetch<AuditEntry[]>("/audit-log?limit=6");
          setAuditorFeed(recent);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      }
    })();
  }, [session]);

  if (!session) return null;

  const chartData = summary
    ? (["open", "accepted", "rejected", "escalated"] as const)
        .map((k) => ({ key: k, value: summary.flags_by_status[k] }))
        .filter((d) => d.value > 0)
    : [];

  return (
    <AuthShell eyebrow="Overview" title="Dashboard">
      {error && <p className="mb-4 rounded-lg bg-bpr-rose/10 p-3 text-sm text-bpr-rose">{error}</p>}
      {!summary && (
        <div className="grid grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      )}

      {summary && session.role === "compliance_officer" && (
        <>
          <div className="grid grid-cols-4 gap-4">
            <StatCard label="Open Flags" value={summary.open_flags_count} icon={ShieldAlert} tone="brass" hint="Awaiting a decision" />
            <StatCard label="Escalated" value={summary.escalated_count} icon={AlarmClockPlus} tone="rose" hint="Needs senior review" />
            <StatCard label="Ingested Today" value={summary.transactions_ingested_today} icon={Inbox} hint="New transactions" />
            <StatCard label="Pending Drafts" value={summary.pending_report_drafts_count} icon={FileClock} hint="Reports awaiting sign-off" />
          </div>

          <div className="mt-5 grid grid-cols-3 gap-5">
            <Card className="col-span-1">
              <h2 className="mb-3 font-display text-[17px] text-bpr-navy">Flags by status</h2>
              {chartData.length === 0 ? (
                <EmptyState title="No flags yet" hint="Run screening from the Screening Queue." />
              ) : (
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={chartData} dataKey="value" nameKey="key" innerRadius={44} outerRadius={64} paddingAngle={3}>
                        {chartData.map((d) => (
                          <Cell key={d.key} fill={CHART_COLORS[d.key]} stroke="none" />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ borderRadius: 8, border: "1px solid #E4DCC8", fontSize: 12, fontFamily: "var(--font-public-sans)" }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                {chartData.map((d) => (
                  <span key={d.key} className="flex items-center gap-1.5 text-[11.5px] text-bpr-ink2/70">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: CHART_COLORS[d.key] }} />
                    {d.key} ({d.value})
                  </span>
                ))}
              </div>
            </Card>

            <Card className="col-span-1">
              <h2 className="mb-1 font-display text-[17px] text-bpr-navy">Needs your attention</h2>
              <p className="mb-3 text-[12px] text-bpr-ink2/50">Open flags, oldest first</p>
              {attention.length === 0 ? (
                <EmptyState title="Queue is clear" />
              ) : (
                <ul className="space-y-2.5">
                  {attention.map((f) => (
                    <li key={f.id} className="flex items-center justify-between gap-2 border-b border-bpr-hairline pb-2.5 last:border-0 last:pb-0">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-medium text-bpr-navy">{f.rule_triggered}</p>
                        <p className="truncate font-mono text-[11px] text-bpr-ink2/45">{f.transaction_ref}</p>
                      </div>
                      <Badge tone={FLAG_STATUS_TONE[f.status]}>{f.status}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="col-span-1">
              <h2 className="mb-3 font-display text-[17px] text-bpr-navy">Recent activity</h2>
              <LedgerFeed entries={summary.recent_audit} />
            </Card>
          </div>
        </>
      )}

      {summary && session.role === "loan_officer" && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="Decisions (7 days)" value={summary.recent_decisions_count} icon={Gavel} hint="Logged by you" />
          </div>
          <div className="mt-5">
            <Card>
              <h2 className="mb-3 font-display text-[17px] text-bpr-navy">Your recent committee decisions</h2>
              {summary.recent_decisions.length === 0 ? (
                <EmptyState title="No decisions logged yet" hint="Log Loan Committee Decision to get started." />
              ) : (
                <ul className="space-y-0">
                  {summary.recent_decisions.map((d, idx) => (
                    <li
                      key={d.id}
                      className={`flex items-center justify-between py-2.5 text-[13px] ${idx !== summary.recent_decisions.length - 1 ? "border-b border-bpr-hairline" : ""}`}
                    >
                      <div className="min-w-0">
                        <p className="font-mono text-[11.5px] text-bpr-ink2/50">{d.customer_ref}</p>
                        <p className="mt-0.5 truncate text-bpr-navy">{d.committee_notes}</p>
                      </div>
                      <Badge tone={FLAG_STATUS_TONE[d.decision] ?? "neutral"}>{d.decision}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}

      {summary && session.role === "auditor" && (
        <>
          <div className="grid grid-cols-4 gap-4">
            <StatCard label="Audit Entries" value={summary.total_audit_entries} icon={ScrollText} hint="All time, append-only" />
            <StatCard label="Actions Today" value={summary.actions_today} icon={Inbox} />
            <StatCard label="Open Flags" value={summary.flags_by_status.open} icon={ShieldAlert} tone="brass" />
            <StatCard label="Escalated" value={summary.flags_by_status.escalated} icon={AlarmClockPlus} tone="rose" />
          </div>
          <div className="mt-5 grid grid-cols-3 gap-5">
            <Card className="col-span-1">
              <h2 className="mb-3 font-display text-[17px] text-bpr-navy">Flags by status</h2>
              {chartData.length === 0 ? (
                <EmptyState title="No flags yet" />
              ) : (
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={chartData} dataKey="value" nameKey="key" innerRadius={44} outerRadius={64} paddingAngle={3}>
                        {chartData.map((d) => (
                          <Cell key={d.key} fill={CHART_COLORS[d.key]} stroke="none" />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #E4DCC8", fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
            <Card className="col-span-2">
              <h2 className="mb-3 font-display text-[17px] text-bpr-navy">Recent activity</h2>
              <LedgerFeed entries={auditorFeed} />
            </Card>
          </div>
        </>
      )}
    </AuthShell>
  );
}
