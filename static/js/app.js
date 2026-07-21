(() => {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const folderInput = document.getElementById("folderInput");
  const btnPilihFile = document.getElementById("btnPilihFile");
  const btnPilihFolder = document.getElementById("btnPilihFolder");
  const fileListWrap = document.getElementById("fileListWrap");
  const fileListUl = document.getElementById("fileListUl");
  const fileCount = document.getElementById("fileCount");
  const btnProses = document.getElementById("btnProses");
  const btnUnduh = document.getElementById("btnUnduh");
  const btnReset = document.getElementById("btnReset");
  const inputBidang = document.getElementById("inputBidang");
  const progressWrap = document.getElementById("progressWrap");
  const progressFill = document.getElementById("progressFill");
  const progressLabel = document.getElementById("progressLabel");
  const tambahFileHint = document.getElementById("tambahFileHint");

  const statTotal = document.getElementById("statTotal");
  const statBerhasil = document.getElementById("statBerhasil");
  const statGagal = document.getElementById("statGagal");
  const statBaris = document.getElementById("statBaris");

  const dataTableBody = document.getElementById("dataTableBody");
  const logList = document.getElementById("logList");

  const statusBadge = document.getElementById("statusBadge");
  const statusBadgeText = document.getElementById("statusBadgeText");

  let filesTerpilih = [];
  let pollTimer = null;
  let sudahPernahProses = false; // sudah pernah menyelesaikan minimal satu batch?

  function setBadge(mode, text) {
    statusBadge.classList.remove("busy", "error");
    if (mode === "busy") statusBadge.classList.add("busy");
    if (mode === "error") statusBadge.classList.add("error");
    statusBadgeText.textContent = text;
  }

  // ---------- Pemilihan file ----------
  function renderFileList() {
    if (filesTerpilih.length === 0) {
      fileListWrap.hidden = true;
      btnProses.disabled = true;
      return;
    }
    fileListWrap.hidden = false;
    fileCount.textContent = filesTerpilih.length;
    fileListUl.innerHTML = "";
    filesTerpilih.slice(0, 200).forEach((f) => {
      const li = document.createElement("li");
      li.textContent = f.webkitRelativePath || f.name;
      fileListUl.appendChild(li);
    });
    btnProses.disabled = false;
  }

  function tambahFile(fileArrayLike) {
    const arr = Array.from(fileArrayLike).filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    filesTerpilih = arr;
    renderFileList();
  }

  btnPilihFile.addEventListener("click", () => fileInput.click());
  btnPilihFolder.addEventListener("click", () => folderInput.click());
  fileInput.addEventListener("change", (e) => tambahFile(e.target.files));
  folderInput.addEventListener("change", (e) => tambahFile(e.target.files));

  ["dragenter", "dragover"].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
    })
  );
  dropZone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length) {
      tambahFile(e.dataTransfer.files);
    }
  });

  // ---------- Upload lalu proses (mendukung penambahan file bertahap) ----------
  btnProses.addEventListener("click", async () => {
    if (filesTerpilih.length === 0) return;
    btnProses.disabled = true;
    btnProses.textContent = "Mengunggah…";
    setBadge("busy", "Mengunggah file…");

    const formData = new FormData();
    filesTerpilih.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!data.ok) {
        alert("Gagal mengunggah: " + (data.pesan || "unknown error"));
        btnProses.disabled = false;
        btnProses.textContent = sudahPernahProses ? "Proses File Baru" : "Proses Semua File";
        setBadge("error", "Gagal unggah");
        return;
      }
      statTotal.textContent = data.total_file;
      progressWrap.hidden = false;
      progressLabel.textContent = `Memproses file baru…`;
      btnProses.textContent = "Memproses…";
      btnUnduh.hidden = true;
      setBadge("busy", "Memproses file…");

      const resProcess = await fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bidang_override: inputBidang.value.trim() }),
      });
      const dataProcess = await resProcess.json();
      if (!dataProcess.ok) {
        alert("Gagal memulai proses: " + (dataProcess.pesan || "unknown error"));
        btnProses.disabled = false;
        btnProses.textContent = sudahPernahProses ? "Proses File Baru" : "Proses Semua File";
        setBadge("error", "Gagal memproses");
        return;
      }

      // file yang baru saja dikirim sudah "diserahkan" ke server, siap-siap
      // untuk seleksi berikutnya begitu batch ini selesai diproses
      filesTerpilih = [];
      fileInput.value = "";
      folderInput.value = "";
      renderFileList();

      mulaiPolling();
    } catch (err) {
      alert("Terjadi kesalahan jaringan lokal: " + err);
      btnProses.disabled = false;
      btnProses.textContent = sudahPernahProses ? "Proses File Baru" : "Proses Semua File";
      setBadge("error", "Terjadi kesalahan");
    }
  });

  function renderPreview(rows) {
    if (!rows || rows.length === 0) return;
    dataTableBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      ["Nama", "NIP", "Golongan", "Tanggal", "Jam Masuk", "Jam Keluar", "Pulang Telat", "Jumlah Jam Kerja", "Keterangan"].forEach((k) => {
        const td = document.createElement("td");
        td.textContent = r[k] ?? "";
        tr.appendChild(td);
      });
      dataTableBody.appendChild(tr);
    });
  }

  function renderLog(log) {
    if (!log || log.length === 0) {
      logList.innerHTML = '<li class="log-empty">Tidak ada catatan kesalahan.</li>';
      return;
    }
    logList.innerHTML = "";
    log
      .slice()
      .reverse()
      .forEach((item) => {
        const li = document.createElement("li");
        li.innerHTML = `<span class="log-file">${item.file}</span><span class="log-msg">${item.pesan}</span>`;
        logList.appendChild(li);
      });
  }

  function mulaiPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      const res = await fetch("/api/status");
      const s = await res.json();

      statTotal.textContent = s.total_file;
      statBerhasil.textContent = s.berhasil;
      statGagal.textContent = s.gagal;
      statBaris.textContent = s.total_baris;

      const pct = s.total_file ? Math.round((s.diproses / s.total_file) * 100) : 0;
      progressFill.style.width = pct + "%";
      progressLabel.textContent = `Memproses ${s.diproses} dari ${s.total_file} file (kumulatif)… (${pct}%)`;

      renderPreview(s.preview);
      renderLog(s.log);

      if (s.status === "done") {
        clearInterval(pollTimer);
        sudahPernahProses = true;
        progressLabel.textContent = `Selesai — ${s.berhasil} berhasil, ${s.gagal} bermasalah/duplikat dari total ${s.total_file} file.`;

        // JANGAN sembunyikan tombol proses secara permanen - biarkan pengguna
        // bisa menambah file susulan kapan saja tanpa perlu mulai ulang.
        btnProses.disabled = true; // nonaktif sampai ada file baru dipilih lagi
        btnProses.textContent = "Proses File Baru";
        if (s.siap_unduh) btnUnduh.hidden = false;
        btnReset.hidden = false;
        if (tambahFileHint) tambahFileHint.hidden = false;
        setBadge(s.gagal > 0 ? "error" : null, s.gagal > 0 ? "Selesai dengan catatan" : "Selesai");
      }
    }, 700);
  }

  btnUnduh.addEventListener("click", () => {
    window.location.href = "/api/download";
  });

  btnReset.addEventListener("click", async () => {
    await fetch("/api/reset", { method: "POST" });
    filesTerpilih = [];
    fileInput.value = "";
    folderInput.value = "";
    renderFileList();
    statTotal.textContent = "0";
    statBerhasil.textContent = "0";
    statGagal.textContent = "0";
    statBaris.textContent = "0";
    progressWrap.hidden = true;
    progressFill.style.width = "0%";
    sudahPernahProses = false;
    btnProses.hidden = false;
    btnProses.disabled = true;
    btnProses.textContent = "Proses Semua File";
    btnUnduh.hidden = true;
    btnReset.hidden = true;
    if (tambahFileHint) tambahFileHint.hidden = true;
    dataTableBody.innerHTML = '<tr class="empty-row"><td colspan="9">Belum ada data. Unggah file PDF untuk memulai.</td></tr>';
    logList.innerHTML = '<li class="log-empty">Tidak ada catatan kesalahan.</li>';
    inputBidang.value = "";
    setBadge(null, "Siap");
  });
})();
