# -*- coding: utf-8 -*-
"""
app.py
------
Backend web lokal untuk Sistem Rekapitulasi Absensi Otomatis
Bidang Daskrimti - Kejaksaan Tinggi Jawa Tengah.

Menjalankan:
    python app.py
lalu buka http://127.0.0.1:5000 di browser.
"""

import os
import hashlib
import threading
import time
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()  # baca file .env (DATABASE_URL, SECRET_KEY, dst) sebelum apa pun lain diinisialisasi

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import pandas as pd

from extractor import ekstrak_pdf
from rekap_resmi import tulis_sheet_rekap_resmi
from db import (
    init_db, get_session, muat_dedup_index,
    BatchProses, AbsensiHarian, RingkasanKehadiran,
    FileHashTerproses, SignaturePegawaiTerproses,
)
from auth import cek_login, login_required

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)
# Kunci untuk menandatangani session cookie (login). WAJIB diisi lewat
# environment variable di produksi - kalau tidak diisi, dipakai nilai
# default hanya supaya tidak crash saat pengembangan lokal awal.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ganti-kunci-ini-di-file-env")
# Batas ukuran total unggahan sekaligus. Dinaikkan ke 2 GB karena untuk ~380
# file PDF absensi (apalagi jika sebagian hasil scan/gambar) 300 MB berisiko
# kurang. Sesuaikan lagi angka ini jika perlu.
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB

# Buat tabel di Supabase (jika belum ada) begitu app pertama kali dijalankan.
# Pastikan DATABASE_URL di .env sudah diisi dengan connection string dari
# Supabase, lihat db.py.
init_db()

# Muat ulang indeks dedup (hash file & signature pegawai) yang sudah pernah
# tersimpan di Supabase sejak sebelumnya - supaya kalau app ini di-restart,
# app TIDAK "lupa" file mana saja yang sudah pernah diproses, dan tidak
# menyimpan ulang baris yang sama ke database.
try:
    _FILE_HASH_INDEX_AWAL, _CONTENT_SIGNATURE_INDEX_AWAL = muat_dedup_index()
except Exception:
    # Kalau Supabase belum siap/gagal konek saat startup, tetap jalan dengan
    # indeks kosong (perilaku dedup akan sepenuhnya in-memory untuk sesi ini).
    _FILE_HASH_INDEX_AWAL, _CONTENT_SIGNATURE_INDEX_AWAL = {}, {}


@app.errorhandler(413)
def terlalu_besar(e):
    """Pesan error yang rapi (bukan halaman error mentah bawaan Flask)
    saat total ukuran file yang diunggah melebihi batas di atas."""
    batas_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify({
        "ok": False,
        "pesan": (
            f"Total ukuran file yang diunggah melebihi batas ({batas_mb} MB). "
            "Coba unggah dalam beberapa kelompok/batch yang lebih kecil, "
            "atau naikkan batas MAX_CONTENT_LENGTH di app.py."
        ),
    }), 413

# Status proses disimpan di memori (cukup untuk pemakaian lokal 1 pengguna).
# Mendukung unggah & proses BERTAHAP: file baru bisa ditambahkan kapan saja
# dan diproses menyusul tanpa menghapus hasil yang sudah ada, sampai
# pengguna menekan "Mulai ulang".
STATE = {
    "status": "idle",          # idle | processing | done
    "total_file": 0,           # jumlah total file unik di folder uploads/ (kumulatif)
    "diproses": 0,             # jumlah file yang sudah dicoba diproses (kumulatif)
    "berhasil": 0,
    "gagal": 0,                # termasuk file gagal dibaca & file/duplikat yang dilewati
    "log": [],                 # list of {file, pesan}
    "hasil_rows": [],          # list of dict baris absensi harian (gabungan seluruh batch)
    "hasil_ringkasan": [],     # list of dict rekap statistik per pegawai (gabungan seluruh batch)
    "bidang_override": "",     # nama Bidang manual (opsional) untuk sheet rekap resmi
    "output_path": None,
    "mulai": None,
    "selesai": None,
    "processed_files": set(),        # nama file yang SUDAH pernah diproses (agar tidak diproses ulang)
    "file_hash_index": dict(_FILE_HASH_INDEX_AWAL),           # sha256(isi file) -> nama file pertama yang punya isi itu
    "content_signature_index": dict(_CONTENT_SIGNATURE_INDEX_AWAL),   # signature(NIP + rincian harian) -> nama file pertama
    "batch_id": None,                # id baris batch_proses di Supabase untuk sesi ini (bisa dipakai berkali-kali sampai reset)
    "admin_username": "",            # username admin yang memicu proses (disalin dari session sebelum thread dimulai)
}
LOCK = threading.Lock()


def reset_state():
    """Reset total: dipakai saat pengguna menekan 'Mulai ulang / unggah batch baru'."""
    with LOCK:
        STATE.update({
            "status": "idle",
            "total_file": 0,
            "diproses": 0,
            "berhasil": 0,
            "gagal": 0,
            "log": [],
            "hasil_rows": [],
            "hasil_ringkasan": [],
            "bidang_override": "",
            "output_path": None,
            "mulai": None,
            "selesai": None,
            "processed_files": set(),
            # file_hash_index & content_signature_index SENGAJA TIDAK direset di sini.
            # Keduanya merepresentasikan apa yang sudah benar-benar tersimpan di
            # MySQL (tabel file_hash_terproses & signature_pegawai_terproses),
            # jadi walau pengguna klik "Mulai ulang", PDF yang isinya sama tetap
            # akan terdeteksi sebagai duplikat dan tidak dobel di database.
            "batch_id": None,
        })
    # bersihkan folder uploads & output supaya benar-benar mulai dari nol
    for folder in (UPLOAD_DIR, OUTPUT_DIR):
        for f in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                pass


def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for potongan in iter(lambda: f.read(1024 * 1024), b""):
            h.update(potongan)
    return h.hexdigest()


def _signature_pegawai(nip, baris_pegawai):
    """Tanda tangan isi data harian satu pegawai (dipakai untuk mendeteksi
    file yang isinya sama meski nama filenya berbeda, mis. hasil ekspor
    ulang). Diambil dari NIP + kumpulan (tanggal, jam masuk, jam keluar,
    keterangan) yang diurutkan, supaya tidak terpengaruh urutan baris."""
    inti = sorted(
        (b.get("Tanggal", ""), b.get("Jam Masuk", ""), b.get("Jam Keluar", ""), b.get("Keterangan", ""))
        for b in baris_pegawai
    )
    teks = (nip or "") + "|" + "|".join(f"{a},{b},{c},{d}" for a, b, c, d in inti)
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("admin_username"):
            return redirect(url_for("index"))
        return render_template("login.html", error=None)

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    admin = cek_login(username, password)
    if not admin:
        return render_template("login.html", error="Username atau password salah."), 401

    session["admin_username"] = admin["username"]
    session["admin_nama"] = admin["nama_lengkap"] or admin["username"]
    tujuan = request.args.get("next") or url_for("index")
    return redirect(tujuan)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", admin_nama=session.get("admin_nama"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", admin_nama=session.get("admin_nama"))


@app.route("/api/upload", methods=["POST"])
@login_required
def upload():
    """Terima file PDF (drag-drop / pilih file / pilih folder).
    Bersifat MENAMBAHKAN ke batch yang sedang berjalan - tidak menghapus
    file yang sebelumnya sudah diunggah/diproses, supaya pengguna bisa
    menambah file susulan tanpa perlu mulai ulang."""
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "pesan": "Tidak ada file yang diterima"}), 400

    disimpan = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            continue
        nama_aman = os.path.basename(f.filename)
        tujuan = os.path.join(UPLOAD_DIR, nama_aman)
        # hindari nama file bentrok (mis. file dengan nama sama diunggah lagi
        # di batch berikutnya) - disimpan dengan akhiran angka, dan akan
        # terdeteksi sebagai duplikat isi saat diproses jika memang sama persis
        i = 1
        base, ext = os.path.splitext(tujuan)
        while os.path.exists(tujuan):
            tujuan = f"{base}_{i}{ext}"
            i += 1
        f.save(tujuan)
        disimpan.append(os.path.basename(tujuan))

    with LOCK:
        total_sekarang = len([f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".pdf")])
        STATE["total_file"] = total_sekarang
        if STATE["status"] == "done":
            STATE["status"] = "idle"  # ada file baru menunggu diproses

    return jsonify({"ok": True, "jumlah": len(disimpan), "files": disimpan, "total_file": total_sekarang})


def _proses_job():
    with LOCK:
        STATE["status"] = "processing"
        if not STATE["mulai"]:
            STATE["mulai"] = datetime.now().strftime("%H:%M:%S")

    daftar_file = sorted(f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".pdf"))

    # Data yang BENAR-BENAR baru pada pemanggilan _proses_job() kali ini saja
    # (bukan kumulatif seperti STATE["hasil_rows"]) - dipakai supaya saat
    # disimpan ke MySQL tidak menyimpan ulang baris dari batch sebelumnya.
    db_rows_baru = []
    db_ringkasan_baru = []
    db_hash_baru = []          # list of (file_hash, nama_file)
    db_signature_baru = []     # list of (signature, nip, nama_file)

    for nama_file in daftar_file:
        with LOCK:
            if nama_file in STATE["processed_files"]:
                continue  # sudah diproses pada batch sebelumnya, lewati
            STATE["processed_files"].add(nama_file)

        path = os.path.join(UPLOAD_DIR, nama_file)

        # --- Lapis 1: deteksi file dengan ISI PERSIS SAMA (hash) ---
        try:
            file_hash = _hash_file(path)
        except OSError as e:
            with LOCK:
                STATE["diproses"] += 1
                STATE["gagal"] += 1
                STATE["log"].append({"file": nama_file, "pesan": f"Tidak bisa membaca file: {e}"})
            continue

        with LOCK:
            STATE["diproses"] += 1
            file_kembar = STATE["file_hash_index"].get(file_hash)
            if file_kembar:
                STATE["gagal"] += 1
                STATE["log"].append({
                    "file": nama_file,
                    "pesan": (
                        f"File duplikat - isi file ini persis sama dengan file yang sudah "
                        f"diunggah sebelumnya ('{file_kembar}'). Dilewati agar tidak dobel di rekap."
                    ),
                })
                continue
            STATE["file_hash_index"][file_hash] = nama_file
            db_hash_baru.append((file_hash, nama_file))

        # --- Ekstraksi ---
        rows, ringkasan, error = ekstrak_pdf(path, nama_file)

        with LOCK:
            if error:
                STATE["gagal"] += 1
                STATE["log"].append({"file": nama_file, "pesan": error})
                continue

            # --- Lapis 2: deteksi DATA yang sama (NIP + rincian harian sama),
            #     berguna kalau file yang sama diekspor ulang dengan nama beda ---
            ringkasan_baru = []
            rows_baru = []
            for r in ringkasan:
                nip = r.get("NIP", "-")
                baris_pegawai = [b for b in rows if b.get("NIP") == nip]
                sig = _signature_pegawai(nip, baris_pegawai)
                file_kembar_konten = STATE["content_signature_index"].get(sig)
                if file_kembar_konten:
                    STATE["log"].append({
                        "file": nama_file,
                        "pesan": (
                            f"Data duplikat - NIP {nip} ({r.get('Nama', '-')}) dengan rincian "
                            f"dan periode yang sama sudah pernah diproses dari file "
                            f"'{file_kembar_konten}'. Data pegawai ini dilewati agar tidak "
                            f"dobel di rekap."
                        ),
                    })
                    continue
                STATE["content_signature_index"][sig] = nama_file
                db_signature_baru.append((sig, nip, nama_file))
                ringkasan_baru.append(r)
                rows_baru.extend(baris_pegawai)

            if ringkasan and not ringkasan_baru:
                # seluruh pegawai di file ini ternyata duplikat konten
                STATE["gagal"] += 1
                continue

            if ringkasan_baru:
                STATE["hasil_rows"].extend(rows_baru)
                STATE["hasil_ringkasan"].extend(ringkasan_baru)
                db_rows_baru.extend(rows_baru)
                db_ringkasan_baru.extend(ringkasan_baru)
            elif rows:
                # kasus jarang: ada baris harian tapi tidak ada ringkasan sama sekali
                STATE["hasil_rows"].extend(rows)
                db_rows_baru.extend(rows)

            STATE["berhasil"] += 1
        time.sleep(0.03)  # jeda kecil agar progress terlihat halus di UI

    # susun ulang file Excel dari SELURUH data terkumpul sejauh ini (semua batch)
    with LOCK:
        if STATE["hasil_rows"]:
            df = pd.DataFrame(STATE["hasil_rows"])
            kolom_urut = [
                "Nama", "NIP", "NRP", "Golongan", "Sub Unit Kerja", "Jabatan",
                "Tanggal", "Jadwal Masuk", "Jadwal Pulang", "Jam Masuk", "Jam Keluar",
                "Datang Awal", "Datang Telat", "Pulang Awal", "Pulang Telat",
                "Jumlah Jam Kerja", "Keterangan", "Sumber File",
            ]
            df = df[[c for c in kolom_urut if c in df.columns]]
            nama_output = f"rekap_absensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            path_output = os.path.join(OUTPUT_DIR, nama_output)

            with pd.ExcelWriter(path_output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Rekap Absensi Harian")
                ws = writer.sheets["Rekap Absensi Harian"]
                for i, col in enumerate(df.columns, start=1):
                    max_len = max([len(str(col))] + [len(str(v)) for v in df[col].astype(str).tolist()[:2000]])
                    huruf = chr(64 + i) if i <= 26 else "A" + chr(64 + i - 26)
                    ws.column_dimensions[huruf].width = min(max_len + 4, 45)

                if STATE["hasil_ringkasan"]:
                    df_ringkasan = pd.DataFrame(STATE["hasil_ringkasan"])
                    kolom_tampil = [c for c in df_ringkasan.columns if not c.startswith("_")]
                    df_ringkasan[kolom_tampil].to_excel(writer, index=False, sheet_name="Ringkasan Kehadiran")
                    ws2 = writer.sheets["Ringkasan Kehadiran"]
                    for i, col in enumerate(kolom_tampil, start=1):
                        max_len = max([len(str(col))] + [len(str(v)) for v in df_ringkasan[col].astype(str).tolist()[:2000]])
                        huruf = chr(64 + i) if i <= 26 else "A" + chr(64 + i - 26)
                        ws2.column_dimensions[huruf].width = min(max_len + 4, 45)

                if STATE["log"]:
                    df_log = pd.DataFrame(STATE["log"])
                    df_log.to_excel(writer, index=False, sheet_name="Log Kesalahan")

                # sheet tambahan: format resmi instansi
                if STATE["hasil_ringkasan"]:
                    semua_tanggal = [r.get("Tanggal") for r in STATE["hasil_rows"]]
                    tulis_sheet_rekap_resmi(
                        writer.book, STATE["hasil_ringkasan"], semua_tanggal,
                        nama_bidang=STATE.get("bidang_override", ""),
                    )

            STATE["output_path"] = path_output

        # --- simpan ke MySQL (buat batch baru kalau ini proses pertama di sesi
        #     ini, atau tambahkan ke batch yang sama kalau ini lanjutan upload) ---
        try:
            session = get_session()
            if STATE["batch_id"] is None:
                batch = BatchProses(
                    bidang_override=STATE.get("bidang_override", ""),
                    total_file=STATE["total_file"],
                    berhasil=STATE["berhasil"],
                    gagal=STATE["gagal"],
                    selesai=datetime.now(),
                    dibuat_oleh=STATE.get("admin_username", ""),
                )
                session.add(batch)
                session.flush()  # supaya batch.id terisi
                STATE["batch_id"] = batch.id
            else:
                batch = session.query(BatchProses).get(STATE["batch_id"])
                batch.total_file = STATE["total_file"]
                batch.berhasil = STATE["berhasil"]
                batch.gagal = STATE["gagal"]
                batch.bidang_override = STATE.get("bidang_override", "")
                batch.selesai = datetime.now()

            for r in db_rows_baru:
                session.add(AbsensiHarian.from_row_dict(r, batch.id))
            for r in db_ringkasan_baru:
                session.add(RingkasanKehadiran.from_ringkasan_dict(r, batch.id))
            for file_hash, nama_file_hash in db_hash_baru:
                session.add(FileHashTerproses(
                    file_hash=file_hash, nama_file=nama_file_hash, batch_id=batch.id
                ))
            for sig, nip, nama_file_sig in db_signature_baru:
                session.add(SignaturePegawaiTerproses(
                    signature=sig, nip=nip, nama_file=nama_file_sig, batch_id=batch.id
                ))

            session.commit()
            session.close()
        except Exception as e:
            # Jangan gagalkan seluruh proses hanya karena DB bermasalah -
            # file Excel tetap tersedia untuk diunduh. Catat saja errornya di log.
            STATE["log"].append({"file": "-", "pesan": f"Gagal menyimpan ke MySQL: {e}"})

        STATE["status"] = "done"
        STATE["selesai"] = datetime.now().strftime("%H:%M:%S")


@app.route("/api/process", methods=["POST"])
@login_required
def process():
    with LOCK:
        if STATE["status"] == "processing":
            return jsonify({"ok": False, "pesan": "Proses sedang berjalan"}), 409
        belum_diproses = [
            f for f in os.listdir(UPLOAD_DIR)
            if f.lower().endswith(".pdf") and f not in STATE["processed_files"]
        ]
        if not belum_diproses:
            return jsonify({"ok": False, "pesan": "Tidak ada file baru untuk diproses"}), 400
        data = request.get_json(silent=True) or {}
        bidang_baru = (data.get("bidang_override") or "").strip()
        if bidang_baru:
            STATE["bidang_override"] = bidang_baru
        # `session` Flask hanya berlaku dalam konteks request, tidak bisa
        # dibaca dari dalam thread latar belakang - jadi disalin ke STATE
        # di sini (masih dalam request ini) sebelum thread-nya dimulai.
        STATE["admin_username"] = session.get("admin_username", "")
    t = threading.Thread(target=_proses_job, daemon=True)
    t.start()
    return jsonify({"ok": True, "jumlah_baru": len(belum_diproses)})


@app.route("/api/status")
@login_required
def status():
    with LOCK:
        preview = STATE["hasil_rows"][-8:] if STATE["hasil_rows"] else []
        return jsonify({
            "status": STATE["status"],
            "total_file": STATE["total_file"],
            "diproses": STATE["diproses"],
            "berhasil": STATE["berhasil"],
            "gagal": STATE["gagal"],
            "total_baris": len(STATE["hasil_rows"]),
            "log": STATE["log"][-30:],
            "preview": preview,
            "mulai": STATE["mulai"],
            "selesai": STATE["selesai"],
            "siap_unduh": STATE["output_path"] is not None,
        })


@app.route("/api/download")
@login_required
def download():
    with LOCK:
        path = STATE["output_path"]
    if not path or not os.path.exists(path):
        return jsonify({"ok": False, "pesan": "Belum ada file hasil untuk diunduh"}), 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.route("/api/reset", methods=["POST"])
@login_required
def reset():
    reset_state()
    return jsonify({"ok": True})


@app.route("/api/riwayat")
@login_required
def riwayat():
    """Daftar batch (sesi) yang pernah tersimpan di MySQL (terbaru dulu)."""
    session = get_session()
    try:
        batch_list = session.query(BatchProses).order_by(BatchProses.id.desc()).limit(50).all()
        hasil = [{
            "id": b.id,
            "bidang_override": b.bidang_override,
            "total_file": b.total_file,
            "berhasil": b.berhasil,
            "gagal": b.gagal,
            "mulai": b.mulai.strftime("%Y-%m-%d %H:%M:%S") if b.mulai else None,
            "selesai": b.selesai.strftime("%Y-%m-%d %H:%M:%S") if b.selesai else None,
            "jumlah_baris_harian": len(b.baris_harian),
            "jumlah_pegawai": len(b.ringkasan),
        } for b in batch_list]
        return jsonify({"ok": True, "riwayat": hasil})
    finally:
        session.close()


@app.route("/api/riwayat/<int:batch_id>")
@login_required
def riwayat_detail(batch_id):
    """Detail satu batch: seluruh baris harian & ringkasan yang tersimpan."""
    session = get_session()
    try:
        batch = session.query(BatchProses).get(batch_id)
        if not batch:
            return jsonify({"ok": False, "pesan": "Batch tidak ditemukan"}), 404

        kolom_harian = ["nama", "nip", "nrp", "golongan", "sub_unit_kerja", "jabatan",
                         "tanggal", "jadwal_masuk", "jadwal_pulang", "jam_masuk", "jam_keluar",
                         "datang_awal", "datang_telat", "pulang_awal", "pulang_telat",
                         "jumlah_jam_kerja", "keterangan", "sumber_file"]
        kolom_ringkasan = ["nama", "nip", "nrp", "golongan", "terlambat", "pulang_cepat",
                            "tidak_absen_datang", "tidak_absen_pulang", "izin", "alpha", "sakit",
                            "dinas_luar", "lepas_piket", "tugas_belajar", "total_cuti",
                            "rincian_cuti", "total_hari_kerja", "sumber_file"]

        baris_harian = [{k: getattr(r, k) for k in kolom_harian} for r in batch.baris_harian]
        ringkasan = [{k: getattr(r, k) for k in kolom_ringkasan} for r in batch.ringkasan]

        return jsonify({"ok": True, "baris_harian": baris_harian, "ringkasan": ringkasan})
    finally:
        session.close()


@app.route("/api/dashboard-data")
@login_required
def dashboard_data():
    """Data agregat untuk halaman dashboard statistik: dipakai grafik
    'jumlah batch per hari' dan 'total kejadian keterlambatan/alpha/dst
    per batch'. Dihitung dari data yang sudah tersimpan di Supabase,
    bukan dari STATE (supaya tetap tampil walau app baru saja restart)."""
    session_db = get_session()
    try:
        batch_list = session_db.query(BatchProses).order_by(BatchProses.id.asc()).all()

        per_batch = []
        for b in batch_list:
            def _jumlah(field):
                total = 0
                for r in b.ringkasan:
                    v = getattr(r, field, None)
                    try:
                        total += int(v)
                    except (TypeError, ValueError):
                        pass
                return total

            per_batch.append({
                "id": b.id,
                "label": (b.selesai or b.mulai).strftime("%d/%m %H:%M") if (b.selesai or b.mulai) else f"Batch {b.id}",
                "bidang_override": b.bidang_override,
                "jumlah_pegawai": len(b.ringkasan),
                "terlambat": _jumlah("terlambat"),
                "alpha": _jumlah("alpha"),
                "sakit": _jumlah("sakit"),
                "izin": _jumlah("izin"),
            })

        return jsonify({
            "ok": True,
            "total_batch": len(batch_list),
            "per_batch": per_batch[-20:],  # 20 batch terakhir supaya grafik tidak terlalu padat
        })
    finally:
        session_db.close()


if __name__ == "__main__":
    print("=" * 60)
    print(" Sistem Rekapitulasi Absensi - Daskrimti Kejati Jateng")
    print(" Buka browser: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)