renderTopbarTokenSettings(document.getElementById("token-settings"));

const SAMPLE = "Nama saya Budi Santoso, NIK saya 3171012303900021. Saya mau komplain karena kartu ATM saya nomor 4532015112830366 tidak bisa dipakai. Alamat saya Jl. Sudirman No 5, RT 03/RW 02, Kelurahan Senayan. Nomor HP saya 081234567890, email budi.santoso@gmail.com. Sudah 3 hari uang saya hilang dari rekening 1234567890, ini sangat mengecewakan.";

document.getElementById("sample-btn").addEventListener("click", () => {
  document.getElementById("text").value = SAMPLE;
});

document.getElementById("ingest-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resultEl = document.getElementById("result");
  const text = document.getElementById("text").value.trim();
  if (!text) return;
  resultEl.innerHTML = `<div class="banner info">Submitting…</div>`;
  try {
    const resp = await Api.ingest(text);
    resultEl.innerHTML = `
      <div class="banner ok">
        Accepted as <code>${resp.job_id}</code> (status: ${resp.status}). Processing runs in the background —
        <a href="detail.html?job_id=${resp.job_id}">open the detail view</a> in a few seconds to see the result.
      </div>`;
  } catch (err) {
    resultEl.innerHTML = `<div class="banner err">${escapeHtml(err.message)}</div>`;
  }
});
