"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import Card from "@/components/Card";
import EmptyState from "@/components/EmptyState";
import Skeleton from "@/components/Skeleton";
import { AuditEntry, apiFetch } from "@/lib/api";

const RANGES: { key: string; label: string; days: number | null }[] = [
  { key: "all", label: "All time", days: null },
  { key: "today", label: "Today", days: 1 },
  { key: "7d", label: "7 days", days: 7 },
  { key: "30d", label: "30 days", days: 30 },
];

function toCsv(entries: AuditEntry[]): string {
  const header = ["timestamp", "actor", "action", "entity_ref", "rationale"];
  const rows = entries.map((e) =>
    [e.timestamp, e.actor, e.action, e.entity_ref ?? "", e.rationale ?? ""]
      .map((v) => `"${String(v).replace(/"/g, '""')}"`)
      .join(",")
  );
  return [header.join(","), ...rows].join("\n");
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actorFilter, setActorFilter] = useState("");
  const [range, setRange] = useState("all");

  async function load() {
    setError(null);
    try {
      const qs = actorFilter ? `?actor=${encodeURIComponent(actorFilter)}` : "";
      const data = await apiFetch<AuditEntry[]>(`/audit-log${qs}`);
      setEntries(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit log");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    if (!entries) return [];
    const rangeDef = RANGES.find((r) => r.key === range);
    if (!rangeDef?.days) return entries;
    const cutoff = Date.now() - rangeDef.days * 24 * 60 * 60 * 1000;
    return entries.filter((e) => new Date(e.timestamp).getTime() >= cutoff);
  }, [entries, range]);

  function exportCsv() {
    const csv = toCsv(filtered);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <AuthShell
      eyebrow="Immutable, append-only"
      title="Audit Explorer"
      action={
        <button
          onClick={exportCsv}
          disabled={filtered.length === 0}
          className="flex items-center gap-2 rounded-lg border border-bpr-hairline bg-bpr-card px-4 py-2.5 text-[13px] font-medium text-bpr-navy transition-colors hover:bg-bpr-parchmentDark disabled:opacity-50"
        >
          <Download className="h-4 w-4" strokeWidth={1.75} />
          Export CSV
        </button>
      }
    >
      {error && <p className="mb-4 rounded-lg bg-bpr-rose/10 p-3 text-sm text-bpr-rose">{error}</p>}

      <div className="mb-5 flex items-center justify-between gap-4">
        <div className="flex gap-1.5">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={`rounded-full px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
                range === r.key ? "bg-bpr-navy text-bpr-parchment" : "bg-bpr-card text-bpr-ink2/70 ring-1 ring-inset ring-bpr-hairline hover:bg-bpr-parchmentDark"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-bpr-ink2/40" />
            <input
              placeholder="Filter by actor"
              value={actorFilter}
              onChange={(e) => setActorFilter(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load()}
              className="w-52 rounded-lg border border-bpr-hairline bg-bpr-card py-1.5 pl-8 pr-3 text-[12.5px] outline-none focus:border-bpr-brass/50"
            />
          </div>
          <button onClick={load} className="rounded-lg bg-bpr-navy px-3.5 py-1.5 text-[12.5px] font-medium text-bpr-parchment hover:bg-bpr-navyLight">
            Search
          </button>
        </div>
      </div>

      {!entries && (
        <div className="space-y-2">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      )}

      {entries && filtered.length === 0 && <EmptyState title="No audit entries match" hint="Adjust the actor filter or date range." />}

      {entries && filtered.length > 0 && (
        <Card>
          <div className="relative pl-5">
            <div className="absolute bottom-2 left-[7px] top-2 w-px bg-bpr-hairline" />
            {filtered.map((e) => (
              <div key={e.id} className="relative mb-4 pl-5 last:mb-0">
                <span className="absolute -left-[3.5px] top-1 h-2.5 w-2.5 rounded-full border-2 border-bpr-card bg-bpr-brass" />
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-[13px]">
                    <span className="font-medium text-bpr-navy">{e.actor}</span>{" "}
                    <span className="text-bpr-ink2/70">{e.action.replace(/_/g, " ")}</span>
                  </p>
                  <span className="shrink-0 whitespace-nowrap text-[11px] text-bpr-ink2/45">{new Date(e.timestamp).toLocaleString()}</span>
                </div>
                {e.entity_ref && <p className="mt-0.5 font-mono text-[11px] text-bpr-ink2/45">{e.entity_ref}</p>}
                {e.rationale && <p className="mt-0.5 text-[12.5px] text-bpr-ink2/65">{e.rationale}</p>}
              </div>
            ))}
          </div>
        </Card>
      )}
    </AuthShell>
  );
}
