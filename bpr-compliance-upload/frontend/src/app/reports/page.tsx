"use client";

import { useState } from "react";
import { Check, FileStack, Sparkles } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import Card from "@/components/Card";
import EmptyState from "@/components/EmptyState";
import { ReportDraft, apiFetch } from "@/lib/api";

export default function ReportsPage() {
  const [period, setPeriod] = useState("2026-08");
  const [draft, setDraft] = useState<ReportDraft | null>(null);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const d = await apiFetch<ReportDraft>("/reports/draft", {
        method: "POST",
        body: JSON.stringify({ period }),
      });
      setDraft(d);
      setActiveSection(Object.keys(d.sections)[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate draft");
    } finally {
      setLoading(false);
    }
  }

  async function approve() {
    if (!draft) return;
    setError(null);
    try {
      const d = await apiFetch<ReportDraft>(`/reports/${draft.id}/approve`, { method: "POST" });
      setDraft(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve");
    }
  }

  const sectionNames = draft ? Object.keys(draft.sections) : [];
  const section = draft && activeSection ? draft.sections[activeSection] : null;

  return (
    <AuthShell
      eyebrow="LBBPR-style drafting"
      title="Report Editor"
      action={
        <div className="flex items-center gap-2">
          <input
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder="YYYY-MM"
            className="w-28 rounded-lg border border-bpr-hairline bg-bpr-card px-3 py-2 text-[13px] outline-none focus:border-bpr-brass/50"
          />
          <button
            onClick={generate}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-bpr-navy px-4 py-2.5 text-[13px] font-medium text-bpr-parchment transition-colors hover:bg-bpr-navyLight disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" strokeWidth={1.75} />
            {loading ? "Drafting..." : "Generate draft"}
          </button>
        </div>
      }
    >
      {error && <p className="mb-4 rounded-lg bg-bpr-rose/10 p-3 text-sm text-bpr-rose">{error}</p>}

      {!draft && <EmptyState title="No draft for this period yet" hint="Pick a period (YYYY-MM) and generate a draft from underlying transaction and loan data." />}

      {draft && (
        <>
          <div className="mb-5 flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-medium ${draft.status === "draft" || draft.status === "approved" ? "bg-bpr-brass text-white" : "bg-bpr-hairline text-bpr-ink2/50"}`}>
                1
              </span>
              <span className="text-[12.5px] font-medium text-bpr-navy">Draft generated</span>
            </div>
            <div className={`h-px w-10 ${draft.status === "approved" ? "bg-bpr-teal" : "bg-bpr-hairline"}`} />
            <div className="flex items-center gap-2">
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-medium ${draft.status === "approved" ? "bg-bpr-teal text-white" : "bg-bpr-hairline text-bpr-ink2/50"}`}>
                {draft.status === "approved" ? <Check className="h-3.5 w-3.5" /> : "2"}
              </span>
              <span className="text-[12.5px] font-medium text-bpr-navy">Compliance sign-off</span>
            </div>
            <span className="ml-auto text-[12px] text-bpr-ink2/50">Period {draft.period}</span>
          </div>

          <div className="grid grid-cols-[240px_1fr] gap-5">
            <Card padded={false} className="h-fit overflow-hidden">
              <div className="border-b border-bpr-hairline px-4 py-3">
                <p className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/55">
                  <FileStack className="h-3.5 w-3.5" strokeWidth={1.75} /> Sections
                </p>
              </div>
              <ul>
                {sectionNames.map((name) => (
                  <li key={name}>
                    <button
                      onClick={() => setActiveSection(name)}
                      className={`flex w-full items-center gap-2 px-4 py-2.5 text-left text-[13px] transition-colors ${
                        activeSection === name ? "bg-bpr-brass/10 text-bpr-navy" : "text-bpr-ink2/70 hover:bg-bpr-parchmentDark/40"
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${activeSection === name ? "bg-bpr-brass" : "bg-bpr-hairline"}`} />
                      <span className="truncate capitalize">{name.replace(/_/g, " ")}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>

            <div className="space-y-4">
              {section && (
                <Card>
                  <h2 className="mb-3 font-display text-[18px] capitalize text-bpr-navy">{activeSection?.replace(/_/g, " ")}</h2>
                  <p className="text-[13.5px] leading-relaxed text-bpr-ink2/85">{section.narrative}</p>
                </Card>
              )}

              {section && (
                <Card className="ledger-rule bg-bpr-card">
                  <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-bpr-ink2/50">Source facts</p>
                  <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[11.5px] leading-[27px] text-bpr-ink2/80">
                    {JSON.stringify(section.source_facts, null, 2)}
                  </pre>
                </Card>
              )}

              {draft.status === "draft" && (
                <button
                  onClick={approve}
                  className="flex items-center gap-2 rounded-lg bg-bpr-teal px-4 py-2.5 text-[13px] font-medium text-white transition-colors hover:opacity-90"
                >
                  <Check className="h-4 w-4" strokeWidth={2} /> Approve &amp; sign off
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </AuthShell>
  );
}
