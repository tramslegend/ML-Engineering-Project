renderTopbarTokenSettings(document.getElementById("token-settings"));

function isoOrDefault(id, fallbackHoursAgo) {
  const v = document.getElementById(id).value;
  if (v) return new Date(v).toISOString();
  const d = new Date(Date.now() - fallbackHoursAgo * 3600 * 1000);
  return d.toISOString();
}

document.getElementById("residency-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("residency-result");
  out.innerHTML = `<div class="banner info">Running…</div>`;
  try {
    const start = isoOrDefault("res-start", 24 * 30);
    const end = isoOrDefault("res-end", 0);
    const r = await Api.residencyReport(start, end);
    out.innerHTML = `
      <div class="stat-row">
        <div class="stat"><div class="n">${r.total_events}</div><div class="l">Total events</div></div>
        <div class="stat"><div class="n">${r.events_leaving_jurisdiction}</div><div class="l">Left jurisdiction</div></div>
        <div class="stat"><div class="n">${r.region}</div><div class="l">Region</div></div>
      </div>
      <pre style="white-space:pre-wrap;font-size:0.8rem;color:var(--text-dim)">${escapeHtml(JSON.stringify(r.events_by_type, null, 2))}</pre>
    `;
  } catch (err) { out.innerHTML = `<div class="banner err">${escapeHtml(err.message)}</div>`; }
});

document.getElementById("incident-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("incident-result");
  out.innerHTML = `<div class="banner info">Running…</div>`;
  try {
    const start = isoOrDefault("inc-start", 24 * 30);
    const end = isoOrDefault("inc-end", 0);
    const r = await Api.incidentScope(start, end);
    out.innerHTML = `
      <div class="banner ok">${r.affected_subject_count} subject(s) affected in this window.</div>
      ${r.affected_subjects.map(s => `<code>${escapeHtml(s)}</code>`).join(" ")}
    `;
  } catch (err) { out.innerHTML = `<div class="banner err">${escapeHtml(err.message)}</div>`; }
});

document.getElementById("subject-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("subject-result");
  const subjectId = document.getElementById("subject-id").value.trim();
  if (!subjectId) return;
  out.innerHTML = `<div class="banner info">Looking up…</div>`;
  try {
    const r = await Api.subjectAccess(subjectId);
    out.innerHTML = r.events.map(ev => `
      <div class="audit-event"><div class="t">${ev.timestamp}</div>${escapeHtml(ev.event_type)} — job <code>${escapeHtml(ev.job_id)}</code></div>
    `).join("") || `<div class="empty">No events for this subject.</div>`;
  } catch (err) { out.innerHTML = `<div class="banner err">${escapeHtml(err.message)}</div>`; }
});

document.getElementById("erase-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("erase-result");
  const subjectId = document.getElementById("erase-subject-id").value.trim();
  const justification = document.getElementById("erase-justification").value.trim();
  if (!subjectId || !justification) {
    out.innerHTML = `<div class="banner err">Subject ID and justification are both required.</div>`;
    return;
  }
  if (!confirm(`Erase all vault entries for ${subjectId}? This orphans every derived token permanently.`)) return;
  out.innerHTML = `<div class="banner info">Erasing…</div>`;
  try {
    const r = await Api.erase(subjectId, justification);
    out.innerHTML = `<div class="banner ok">Erased. ${r.tokens_orphaned} token(s) orphaned for subject ${escapeHtml(r.subject_id)}.</div>`;
  } catch (err) { out.innerHTML = `<div class="banner err">${escapeHtml(err.message)}</div>`; }
});

async function loadOpsConfig() {
  const out = document.getElementById("ops-config");
  try {
    const cfg = await Api.opsConfig();
    out.innerHTML = `
      <div class="field-label">Escalation confidence threshold: ${cfg.escalation_confidence_threshold}</div>
      <form class="inline" id="threshold-form" style="margin-bottom:14px">
        <input type="text" id="threshold-input" value="${cfg.escalation_confidence_threshold}" style="width:70px" />
        <button type="submit">Update</button>
      </form>
      <div class="field-label">Kill switch (disables all external egress)</div>
      <div class="actions">
        <button id="kill-on-btn" class="btn danger" ${cfg.escalation_kill_switch ? "disabled" : ""}>Engage</button>
        <button id="kill-off-btn" class="btn secondary" ${cfg.escalation_kill_switch ? "" : "disabled"}>Disengage</button>
        <span class="pill ${cfg.escalation_kill_switch ? "high" : "low"}" style="align-self:center">${cfg.escalation_kill_switch ? "ENGAGED" : "off"}</span>
      </div>
    `;
    document.getElementById("threshold-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const v = parseFloat(document.getElementById("threshold-input").value);
      await Api.setThreshold(v);
      loadOpsConfig();
    });
    document.getElementById("kill-on-btn").addEventListener("click", async () => { await Api.setKillSwitch(true); loadOpsConfig(); });
    document.getElementById("kill-off-btn").addEventListener("click", async () => { await Api.setKillSwitch(false); loadOpsConfig(); });
  } catch (err) { out.innerHTML = `<div class="banner err">${escapeHtml(err.message)}</div>`; }
}

async function loadCost() {
  const out = document.getElementById("cost-result");
  try {
    const c = await Api.cost();
    out.innerHTML = `<div class="stat"><div class="n">$${c.total_cost_usd.toFixed(4)}</div><div class="l">Total escalation spend (all time)</div></div>`;
  } catch (err) { out.innerHTML = `<div class="banner err">${escapeHtml(err.message)}</div>`; }
}

loadOpsConfig();
loadCost();
