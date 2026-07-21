(() => {
  const dashTotalBatch = document.getElementById("dashTotalBatch");
  const dashPegawaiTerakhir = document.getElementById("dashPegawaiTerakhir");
  const dashTotalAlpha = document.getElementById("dashTotalAlpha");
  const dashTotalTerlambat = document.getElementById("dashTotalTerlambat");
  const dashEmptyNote = document.getElementById("dashEmptyNote");

  const warnaPrimary = "#1F4E37";
  const warnaGold = "#A6813E";
  const warnaDanger = "#B23A2E";

  async function muatData() {
    const res = await fetch("/api/dashboard-data");
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
    const data = await res.json();
    if (!data.ok) return;

    dashTotalBatch.textContent = data.total_batch;

    const perBatch = data.per_batch || [];
    if (perBatch.length === 0) {
      dashEmptyNote.hidden = false;
      return;
    }

    const terakhir = perBatch[perBatch.length - 1];
    dashPegawaiTerakhir.textContent = terakhir.jumlah_pegawai;
    dashTotalAlpha.textContent = perBatch.reduce((a, b) => a + b.alpha, 0);
    dashTotalTerlambat.textContent = perBatch.reduce((a, b) => a + b.terlambat, 0);

    const labels = perBatch.map((b) => b.label);

    new Chart(document.getElementById("chartTren"), {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "Terlambat", data: perBatch.map((b) => b.terlambat), borderColor: warnaGold, backgroundColor: warnaGold, tension: 0.25 },
          { label: "Alpha", data: perBatch.map((b) => b.alpha), borderColor: warnaDanger, backgroundColor: warnaDanger, tension: 0.25 },
          { label: "Sakit", data: perBatch.map((b) => b.sakit), borderColor: warnaPrimary, backgroundColor: warnaPrimary, tension: 0.25 },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
        scales: { y: { beginAtZero: true } },
      },
    });

    new Chart(document.getElementById("chartPegawai"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Jumlah Pegawai", data: perBatch.map((b) => b.jumlah_pegawai), backgroundColor: warnaPrimary },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  muatData();
})();
