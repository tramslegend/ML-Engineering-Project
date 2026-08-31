export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8010";

export type Role = "loan_officer" | "compliance_officer" | "auditor";

export interface Session {
  access_token: string;
  role: Role;
  name: string;
}

const SESSION_KEY = "bpr_session";

export function saveSession(session: Session) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }
}

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  return raw ? (JSON.parse(raw) as Session) : null;
}

export function clearSession() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(SESSION_KEY);
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const session = getSession();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function login(auth_provider_id: string, password: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ auth_provider_id, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return (await res.json()) as Session;
}

export interface Flag {
  id: string;
  transaction_ref: string;
  rule_triggered: string;
  agent_rationale: string | null;
  reviewer_verdict: string | null;
  status: "open" | "accepted" | "rejected" | "escalated";
  decided_by: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface ReportDraft {
  id: string;
  period: string;
  sections: Record<string, { narrative: string; source_facts: Record<string, unknown> }>;
  status: "draft" | "approved";
  generated_by: string;
  approved_by: string | null;
  created_at: string;
  approved_at: string | null;
}

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  entity_ref: string | null;
  rationale: string | null;
  timestamp: string;
}

export interface LoanDecisionRecord {
  id: string;
  customer_ref: string;
  committee_notes: string;
  decision: string;
  decided_by: string;
  timestamp: string;
}

export interface Transaction {
  id: string;
  customer_ref: string;
  amount: number;
  type: string;
  timestamp: string;
  source_file: string;
}

export interface CustomerHistory {
  customer_ref: string;
  pseudonymized_id: string;
  risk_profile: string;
  transactions: Transaction[];
  flags: Flag[];
}

export interface FlagsByStatus {
  open: number;
  accepted: number;
  rejected: number;
  escalated: number;
}

export interface DashboardSummary {
  role: Role;
  flags_by_status: FlagsByStatus;
  open_flags_count: number;
  escalated_count: number;
  transactions_ingested_today: number;
  pending_report_drafts_count: number;
  recent_audit: AuditEntry[];
  recent_decisions_count: number;
  recent_decisions: LoanDecisionRecord[];
  total_audit_entries: number;
  actions_today: number;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>("/dashboard/summary");
}

export async function getCustomerHistory(customerRef: string): Promise<CustomerHistory | null> {
  try {
    return await apiFetch<CustomerHistory>(`/customers/${encodeURIComponent(customerRef)}/history`);
  } catch (err) {
    if (err instanceof Error && err.message.startsWith("404")) return null;
    throw err;
  }
}

export async function listLoanDecisions(customerRef?: string): Promise<LoanDecisionRecord[]> {
  const qs = customerRef ? `?customer_ref=${encodeURIComponent(customerRef)}` : "";
  return apiFetch<LoanDecisionRecord[]>(`/loan-decisions${qs}`);
}

export type ChartType =
  | "bar"
  | "pie"
  | "line"
  | "area"
  | "radar"
  | "radialbar"
  | "treemap"
  | "funnel"
  | "wordcloud"
  | "heatmap"
  | "stackedbar"
  | "sankey"
  | "scatter";

export interface ChartDataPoint {
  label?: string;
  row?: string;
  col?: string;
  x?: number;
  y?: number;
  value?: number;
}

export interface AnalysisResult {
  question: string;
  sql_result: string;
  python_result: string;
  chart_data: ChartDataPoint[] | null;
  chart_type: ChartType | null;
  final_answer: string;
}

export async function runAnalysis(question: string, threadId: string): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>("/analysis/query", {
    method: "POST",
    body: JSON.stringify({ question, thread_id: threadId }),
  });
}
