"use client";

import { useEffect, useState } from "react";
import { Gavel, Search, UserRoundSearch } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import Card from "@/components/Card";
import Badge, { FLAG_STATUS_TONE } from "@/components/Badge";
import EmptyState from "@/components/EmptyState";
import { CustomerHistory, LoanDecisionRecord, apiFetch, getCustomerHistory, listLoanDecisions } from "@/lib/api";

export default function LoanDecisionsPage() {
  const [customerRef, setCustomerRef] = useState("");
  const [notes, setNotes] = useState("");
  const [decision, setDecision] = useState("approved");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [history, setHistory] = useState<CustomerHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [recent, setRecent] = useState<LoanDecisionRecord[]>([]);

  async function loadRecent() {
    try {
      setRecent(await listLoanDecisions());
    } catch {
      // non-fatal: recent-decisions ledger is a convenience panel
    }
  }

  useEffect(() => {
    loadRecent();
  }, []);

  useEffect(() => {
    if (customerRef.trim().length < 4) {
      setHistory(null);
      return;
    }
    setHistoryLoading(true);
    const handle = setTimeout(async () => {
      const h = await getCustomerHistory(customerRef.trim());
      setHistory(h);
      setHistoryLoading(false);
    }, 350);
    return () => clearTimeout(handle);
  }, [customerRef]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setSubmitting(true);
    try {
      await apiFetch("/loan-decisions", {
        method: "POST",
        body: JSON.stringify({ customer_ref: customerRef, committee_notes: notes, decision }),
      });
      setResult("Decision logged and written to the audit trail.");
      setNotes("");
      await loadRecent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to log decision");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell eyebrow="Committee logging" title="Log Loan Committee Decision">
      <div className="grid grid-cols-[1fr_360px] gap-5">
        <Card>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-bpr-ink2/70">Customer ID (pseudonymized)</label>
              <input
                value={customerRef}
                onChange={(e) => setCustomerRef(e.target.value)}
                required
                placeholder="e.g. a88d52d0-... or DASH-xxxxxxxx"
                className="w-full rounded-lg border border-bpr-hairline bg-bpr-card px-3 py-2.5 font-mono text-[12.5px] outline-none focus:border-bpr-brass/50"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-bpr-ink2/70">Decision</label>
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value)}
                className="w-full rounded-lg border border-bpr-hairline bg-bpr-card px-3 py-2.5 text-[13px] outline-none focus:border-bpr-brass/50"
              >
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="deferred">Deferred</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-bpr-ink2/70">Committee notes / rationale</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                required
                rows={5}
                className="w-full rounded-lg border border-bpr-hairline bg-bpr-card px-3 py-2.5 text-[13px] outline-none focus:border-bpr-brass/50"
              />
            </div>
            {error && <p className="rounded-lg bg-bpr-rose/10 px-3 py-2 text-[12.5px] text-bpr-rose">{error}</p>}
            {result && <p className="rounded-lg bg-bpr-teal/10 px-3 py-2 text-[12.5px] text-bpr-teal">{result}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center gap-2 rounded-lg bg-bpr-brass px-4 py-2.5 text-[13px] font-medium text-white transition-colors hover:bg-bpr-brassLight disabled:opacity-50"
            >
              <Gavel className="h-4 w-4" strokeWidth={1.75} />
              {submitting ? "Logging..." : "Log decision"}
            </button>
          </form>
        </Card>

        <div className="space-y-5">
          <Card>
            <p className="mb-3 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/55">
              <UserRoundSearch className="h-3.5 w-3.5" strokeWidth={1.75} /> Customer flag history
            </p>
            {customerRef.trim().length < 4 && (
              <p className="flex items-center gap-2 text-[12.5px] text-bpr-ink2/45">
                <Search className="h-3.5 w-3.5" /> Type a customer ID to look up their record
              </p>
            )}
            {customerRef.trim().length >= 4 && historyLoading && <p className="text-[12.5px] text-bpr-ink2/45">Searching...</p>}
            {customerRef.trim().length >= 4 && !historyLoading && !history && (
              <p className="text-[12.5px] text-bpr-ink2/45">No matching customer found.</p>
            )}
            {history && (
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <span className="font-mono text-[11.5px] text-bpr-ink2/55">{history.pseudonymized_id}</span>
                  <Badge tone="neutral">{history.risk_profile}</Badge>
                </div>
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/50">
                  {history.flags.length} flag{history.flags.length === 1 ? "" : "s"} · {history.transactions.length} transaction
                  {history.transactions.length === 1 ? "" : "s"}
                </p>
                {history.flags.length === 0 ? (
                  <p className="mt-2 text-[12.5px] text-bpr-ink2/45">No screening flags on record.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {history.flags.slice(0, 5).map((f) => (
                      <li key={f.id} className="flex items-center justify-between border-b border-bpr-hairline pb-2 text-[12.5px] last:border-0">
                        <span className="truncate text-bpr-navy">{f.rule_triggered}</span>
                        <Badge tone={FLAG_STATUS_TONE[f.status]}>{f.status}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </Card>

          <Card>
            <p className="mb-3 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/55">Recent committee decisions</p>
            {recent.length === 0 ? (
              <EmptyState title="No decisions logged yet" />
            ) : (
              <ul className="space-y-2">
                {recent.slice(0, 6).map((d) => (
                  <li key={d.id} className="border-b border-bpr-hairline pb-2 text-[12.5px] last:border-0">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] text-bpr-ink2/50">{d.customer_ref.slice(0, 8)}...</span>
                      <Badge tone={FLAG_STATUS_TONE[d.decision] ?? "neutral"}>{d.decision}</Badge>
                    </div>
                    <p className="mt-0.5 truncate text-bpr-ink2/70">{d.committee_notes}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </AuthShell>
  );
}
