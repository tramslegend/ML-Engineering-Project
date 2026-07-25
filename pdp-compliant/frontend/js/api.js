// Thin fetch wrapper for the Sentinel API. Dev-only bearer tokens are kept
// in localStorage and entered via the topbar token settings — see
// backend/app/auth.py for what these stand in for (a real IdP/OIDC principal).

const API_BASE = window.SENTINEL_API_BASE || "http://127.0.0.1:8000";

const TokenStore = {
  get analyst() { return localStorage.getItem("sentinel_analyst_token") || "dev-analyst-token"; },
  set analyst(v) { localStorage.setItem("sentinel_analyst_token", v); },
  get reidentify() { return localStorage.getItem("sentinel_reidentify_token") || "dev-reidentify-token"; },
  set reidentify(v) { localStorage.setItem("sentinel_reidentify_token", v); },
};

async function apiCall(path, { method = "GET", body, scope = "analyst" } = {}) {
  const token = scope === "reidentify" ? TokenStore.reidentify : TokenStore.analyst;
  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const isJson = resp.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await resp.json() : await resp.text();
  if (!resp.ok) {
    const msg = typeof data === "object" && data?.detail ? data.detail : String(data);
    throw new Error(`${resp.status}: ${msg}`);
  }
  return data;
}

const Api = {
  health: () => apiCall("/api/health"),
  ingest: (text) => apiCall("/api/complaints", { method: "POST", body: { text } }),
  list: (status) => apiCall(`/api/complaints${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  detail: (jobId) => apiCall(`/api/complaints/${jobId}`),
  review: (jobId, submission) => apiCall(`/api/complaints/${jobId}/review`, { method: "POST", body: submission }),
  reidentify: (jobId, fields, justification) =>
    apiCall(`/api/complaints/${jobId}/reidentify`, {
      method: "POST",
      scope: "reidentify",
      body: { job_id: jobId, fields: fields?.length ? fields : null, justification },
    }),
  reviewQueue: () => apiCall("/api/review-queue"),
  auditTrail: (jobId) => apiCall(`/api/compliance/audit-trail/${jobId}`),
  auditIntegrity: () => apiCall("/api/compliance/audit-integrity"),
  residencyReport: (start, end) => apiCall(`/api/compliance/residency-report?start=${start}&end=${end}`),
  incidentScope: (start, end) => apiCall(`/api/compliance/incident-scope?start=${start}&end=${end}`),
  subjectAccess: (subjectId) => apiCall(`/api/compliance/subject-access/${subjectId}`),
  erase: (subjectId, justification) =>
    apiCall(`/api/compliance/erase/${subjectId}`, { method: "POST", scope: "reidentify", body: { justification } }),
  opsConfig: () => apiCall("/api/ops/config"),
  setThreshold: (v) => apiCall("/api/ops/config/escalation-threshold", { method: "POST", body: { escalation_confidence_threshold: v } }),
  setKillSwitch: (engaged) => apiCall("/api/ops/config/kill-switch", { method: "POST", body: { engaged } }),
  cost: (jobId) => apiCall(`/api/ops/cost${jobId ? `?job_id=${jobId}` : ""}`),
};

function renderTopbarTokenSettings(container) {
  container.innerHTML = `
    <div class="token-settings">
      <label>Analyst</label>
      <input id="tok-analyst" type="text" value="${TokenStore.analyst}" />
      <label>Re-ID</label>
      <input id="tok-reid" type="text" value="${TokenStore.reidentify}" />
      <button id="tok-save">Save</button>
    </div>`;
  container.querySelector("#tok-save").addEventListener("click", () => {
    TokenStore.analyst = container.querySelector("#tok-analyst").value.trim();
    TokenStore.reidentify = container.querySelector("#tok-reid").value.trim();
    location.reload();
  });
}

function timeAgo(seconds) {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function escapeHtml(s) {
  return (s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
