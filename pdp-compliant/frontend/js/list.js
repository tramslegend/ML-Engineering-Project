renderTopbarTokenSettings(document.getElementById("token-settings"));

const rowsEl = document.getElementById("rows");
const emptyEl = document.getElementById("empty");
const statsEl = document.getElementById("stats");

function pillClass(severity) {
  return severity ? `pill ${severity}` : "pill status";
}

async function loadStats() {
  try {
    const [queue, cost] = await Promise.all([Api.reviewQueue(), Api.cost()]);
    statsEl.innerHTML = `
      <div class="stat"><div class="n">${queue.depth}</div><div class="l">Review queue depth</div></div>
      <div class="stat"><div class="n">${queue.depth ? timeAgo(queue.oldest_age_seconds) : "—"}</div><div class="l">Oldest item age</div></div>
      <div class="stat"><div class="n">$${cost.total_cost_usd.toFixed(4)}</div><div class="l">Total escalation cost</div></div>
    `;
  } catch (e) {
    statsEl.innerHTML = `<div class="banner err">Could not load stats: ${escapeHtml(e.message)}</div>`;
  }
}

async function loadList() {
  const status = document.getElementById("status-filter").value;
  rowsEl.innerHTML = `<tr><td colspan="6" class="empty">Loading…</td></tr>`;
  try {
    const items = await Api.list(status || undefined);
    rowsEl.innerHTML = "";
    emptyEl.style.display = items.length ? "none" : "block";
    for (const item of items) {
      const tr = document.createElement("tr");
      tr.className = "clickable";
      tr.innerHTML = `
        <td><code>${item.job_id}</code></td>
        <td><span class="pill status">${item.status}</span></td>
        <td>${item.category ? escapeHtml(item.category) : "—"}</td>
        <td>${item.severity ? `<span class="${pillClass(item.severity)}">${item.severity}</span>` : "—"}</td>
        <td>${timeAgo(item.age_seconds)}</td>
        <td>${item.guardrail_flags.map(f => `<span class="flag">${escapeHtml(f)}</span>`).join("") || "—"}</td>
      `;
      tr.addEventListener("click", () => { location.href = `detail.html?job_id=${item.job_id}`; });
      rowsEl.appendChild(tr);
    }
  } catch (e) {
    rowsEl.innerHTML = `<tr><td colspan="6"><div class="banner err">Failed to load: ${escapeHtml(e.message)}</div></td></tr>`;
  }
}

document.getElementById("filter-form").addEventListener("submit", (e) => { e.preventDefault(); loadList(); });
document.getElementById("refresh-btn").addEventListener("click", loadList);

loadStats();
loadList();
setInterval(() => { loadStats(); loadList(); }, 8000);
