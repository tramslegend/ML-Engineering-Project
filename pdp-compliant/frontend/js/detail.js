renderTopbarTokenSettings(document.getElementById("token-settings"));

const params = new URLSearchParams(location.search);
const jobId = params.get("job_id");
const contentEl = document.getElementById("content");

const ENTITY_TYPES = ["ORANG", "NIK", "NPWP", "NOMOR_KK", "BPJS", "REKENING", "KARTU", "TELEPON", "EMAIL", "ALAMAT", "PLAT", "TANGGAL_LAHIR", "INSTANSI"];

function tokenTypesPresent(tokensPresent) {
  const types = new Set();
  for (const t of tokensPresent) {
    const m = t.match(/^\[([A-Z_]+)_\d+\]$/);
    if (m) types.add(m[1]);
  }
  return [...types];
}

// F10.3: renders tokenized text with tokens as highlighted chips. `resolved`
// maps token string -> real value, for fields the analyst has re-identified
// in this session (never persisted — see F7.4).
function renderComplaintText(tokenizedText, resolved = {}) {
  if (!tokenizedText) return "<em>not yet tokenized</em>";
  const escaped = escapeHtml(tokenizedText);
  return escaped.replace(/\[([A-Z_]+)_(\d+)\]/g, (full) => {
    if (resolved[full]) {
      return `<span class="token-chip resolved" title="re-identified">${escapeHtml(resolved[full])}</span>`;
    }
    return `<span class="token-chip" title="tokenized, not re-identified">${full}</span>`;
  });
}

let sessionResolved = {}; // token -> real value, this-session-only per F7.4

async function load() {
  if (!jobId) { contentEl.innerHTML = `<div class="banner err">Missing job_id in URL.</div>`; return; }
  try {
    const d = await Api.detail(jobId);
    render(d);
  } catch (e) {
    contentEl.innerHTML = `<div class="banner err">Failed to load: ${escapeHtml(e.message)}</div>`;
  }
}

function render(d) {
  const triage = d.triage;
  const types = tokenTypesPresent(d.tokens_present);
  const canReview = d.status === "pending_review";

  contentEl.innerHTML = `
    <div class="card">
      <h1>${d.job_id}</h1>
      <div class="subtitle">
        <span class="pill status">${d.status}</span>
        ${d.subject_id ? ` · subject <code>${d.subject_id}</code>` : ""}
        · <a href="compliance.html?job_id=${d.job_id}">audit trail for this item</a>
      </div>
      ${d.guardrail_flags.length ? `<div>${d.guardrail_flags.map(f => `<span class="flag">${escapeHtml(f)}</span>`).join("")}</div>` : ""}
      ${d.escalation_reason ? `<div class="banner info" style="margin-top:10px">Escalated to frontier tier — reason: ${escapeHtml(d.escalation_reason)}</div>` : ""}
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>Complaint (tokenized)</h2>
        <div class="complaint-text" id="complaint-text">${renderComplaintText(d.tokenized_text, sessionResolved)}</div>

        <div style="margin-top:16px">
          <div class="field-label">Re-identify (F7 — logged, justification required)</div>
          <div id="reid-fields" style="margin:8px 0">
            ${types.map(t => `<label style="margin-right:10px"><input type="checkbox" class="reid-type" value="${t}"> ${t}</label>`).join("") || "<em>no tokens present</em>"}
          </div>
          <input type="text" id="reid-justification" placeholder="Justification (required, audited)" />
          <div class="actions">
            <button id="reid-selected-btn" class="btn secondary">Reveal selected fields</button>
            <button id="reid-all-btn">Reveal all fields</button>
          </div>
          <div id="reid-result"></div>
        </div>
      </div>

      <div class="card">
        <h2>Triage</h2>
        ${triage ? `
          <div class="field-label">Category</div><div class="field-value">${escapeHtml(triage.category)}</div>
          <div class="field-label">Severity</div><div class="field-value"><span class="pill ${triage.severity}">${triage.severity}</span></div>
          <div class="field-label">Summary</div><div class="field-value">${renderComplaintText(triage.summary, sessionResolved)}</div>
          <div class="field-label">Draft response</div>
          <div class="field-value"><textarea id="draft-response" rows="4">${escapeHtml(triage.draft_response)}</textarea></div>
          <div class="field-label">Confidence</div>
          <div class="field-value">overall ${(triage.overall_confidence * 100).toFixed(0)}% · tier: ${triage.tier_used}</div>
        ` : `<div class="empty">No triage result yet — still processing, or blocked before inference.</div>`}

        ${triage ? `
          <div class="actions">
            <button id="accept-btn" ${canReview ? "" : "disabled"}>Accept</button>
            <button id="edit-btn" class="btn secondary" ${canReview ? "" : "disabled"}>Save edit</button>
            <button id="reject-btn" class="btn danger" ${canReview ? "" : "disabled"}>Reject</button>
          </div>
          ${!canReview ? `<div class="subtitle" style="margin-top:8px">Review actions available once status is <code>pending_review</code>.</div>` : ""}
        ` : ""}
        <div id="review-result"></div>
      </div>
    </div>
  `;

  wireReidentify(d, types);
  if (triage) wireReview(d);
}

function wireReidentify(d, types) {
  const resultEl = document.getElementById("reid-result");

  async function doReidentify(fields) {
    const justification = document.getElementById("reid-justification").value.trim();
    if (!justification) {
      resultEl.innerHTML = `<div class="banner err">Justification is required (F7.3 — every re-identification is audited with actor, subject, and justification).</div>`;
      return;
    }
    resultEl.innerHTML = `<div class="banner info">Requesting…</div>`;
    try {
      const resp = await Api.reidentify(d.job_id, fields, justification);
      // Map resolved real values back onto the tokens that produced them by
      // diffing tokenized vs reidentified text isn't reliable across
      // arbitrary tokens, so instead we re-fetch and substitute per-type:
      // simplest correct approach is to ask the API again per exact token.
      resultEl.innerHTML = `<div class="banner ok">Resolved: ${resp.fields_resolved.join(", ") || "(none matched)"}. Shown below — not saved anywhere.</div>
        <div class="complaint-text" style="margin-top:10px">${escapeHtml(resp.reidentified_text)}</div>`;
    } catch (e) {
      resultEl.innerHTML = `<div class="banner err">${escapeHtml(e.message)}</div>`;
    }
  }

  document.getElementById("reid-selected-btn").addEventListener("click", () => {
    const selected = [...document.querySelectorAll(".reid-type:checked")].map(el => el.value);
    if (!selected.length) { resultEl.innerHTML = `<div class="banner err">Select at least one field.</div>`; return; }
    doReidentify(selected);
  });
  document.getElementById("reid-all-btn").addEventListener("click", () => doReidentify(null));
}

function wireReview(d) {
  const resultEl = document.getElementById("review-result");

  async function submit(decision) {
    const body = { decision, analyst_id: "dev-analyst" };
    if (decision === "edit") {
      body.edited_output = { ...d.triage, draft_response: document.getElementById("draft-response").value };
    }
    if (decision === "reject") {
      body.justification = prompt("Reason for rejection?") || "";
    }
    resultEl.innerHTML = `<div class="banner info">Submitting…</div>`;
    try {
      const resp = await Api.review(d.job_id, body);
      resultEl.innerHTML = `<div class="banner ok">Recorded: ${resp.status}</div>`;
      setTimeout(load, 800);
    } catch (e) {
      resultEl.innerHTML = `<div class="banner err">${escapeHtml(e.message)}</div>`;
    }
  }

  document.getElementById("accept-btn").addEventListener("click", () => submit("accept"));
  document.getElementById("edit-btn").addEventListener("click", () => submit("edit"));
  document.getElementById("reject-btn").addEventListener("click", () => submit("reject"));
}

load();
