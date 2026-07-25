renderTopbarTokenSettings(document.getElementById("token-settings"));

const jobId = new URLSearchParams(location.search).get("job_id");
const contentEl = document.getElementById("content");

async function load() {
  if (!jobId) { contentEl.innerHTML = `<div class="banner err">Missing job_id in URL.</div>`; return; }
  try {
    const [trail, integrity] = await Promise.all([Api.auditTrail(jobId), Api.auditIntegrity()]);
    contentEl.innerHTML = `
      <div class="card">
        <h1>Audit trail — ${jobId}</h1>
        <div class="subtitle">F10.5: read-only. ${trail.event_count} event(s). Hash-chain integrity: ${integrity.intact ? '<span class="flag ok">intact</span>' : '<span class="flag">TAMPERED</span>'}</div>
      </div>
      <div class="card">
        ${trail.events.map(ev => `
          <div class="audit-event">
            <div class="t">${ev.timestamp}</div>
            <strong>${escapeHtml(ev.event_type)}</strong> — actor: <code>${escapeHtml(ev.actor)}</code>
            ${ev.subject_id ? ` · subject <code>${escapeHtml(ev.subject_id)}</code>` : ""}
          </div>
        `).join("") || `<div class="empty">No events recorded yet.</div>`}
      </div>
    `;
  } catch (e) {
    contentEl.innerHTML = `<div class="banner err">Failed to load: ${escapeHtml(e.message)}</div>`;
  }
}

load();
