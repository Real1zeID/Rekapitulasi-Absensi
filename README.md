# Sistem Rekapitulasi Absensi Otomatis
### Bidang Daskrimti — Kejaksaan Tinggi Jawa Tengah (Prototipe Web Lokal)

Aplikasi ini membaca banyak file PDF absensi pegawai sekaligus, mengekstraksi
datanya secara otomatis, dan menggabungkannya menjadi **satu file rekap
Excel** — menggantikan proses pengecekan manual satu per satu.

Versi ini **berbasis web tapi berjalan 100% lokal di komputer sendiri**
(bukan di-hosting online), sehingga data pegawai tidak pernah keluar dari
perangkat kalian.

---

## 1. Yang perlu disiapkan (sekali saja)

1. **Python 3.10 ke atas** — cek dengan `python --version` di terminal.
   Kalau belum ada, unduh di [python.org/downloads](https://www.python.org/downloads/)
   (saat instalasi di Windows, centang **"Add Python to PATH"**).
2. **Visual Studio Code** — [code.visualstudio.com](https://code.visualstudio.com/)
3. Ekstensi **Python** dari Microsoft di VS Code (buka tab Extensions, cari "Python", Install).

---

## 2. Membuka proyek di VS Code

1. Ekstrak (unzip) folder proyek ini di lokasi mana saja, misalnya di Desktop.
2. Buka VS Code → `File` → `Open Folder...` → pilih folder `absensi-web`.
3. Buka terminal bawaan VS Code: menu `Terminal` → `New Terminal`
   (atau tekan `` Ctrl+` ``).

---

## 3. Menyiapkan environment Python (hanya sekali di awal)

Di terminal VS Code, jalankan baris berikut satu per satu:

```bash
# 1. Buat virtual environment (folder khusus paket python untuk proyek ini)
python -m venv venv

# 2. Aktifkan virtual environment
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (Command Prompt):
venv\Scripts\activate.bat
# macOS / Linux:
source venv/bin/activate

# 3. Install semua paket yang dibutuhkan
pip install -r requirements.txt
```

Jika berhasil, di depan baris terminal akan muncul tanda `(venv)`.
Setelah ini, di VS Code bagian kanan bawah pastikan Python Interpreter yang
dipakai adalah `./venv/...` (klik untuk memilih jika belum sesuai).

---

## 3b. Menyiapkan database Supabase (pengganti MySQL/XAMPP)

Versi ini sudah tidak memakai MySQL lokal lagi — database-nya sekarang
**Supabase** (PostgreSQL terkelola di cloud), supaya nanti kalau aplikasinya
mau diakses lebih dari satu komputer, datanya sudah terpusat.

1. Buat akun & project baru di [supabase.com](https://supabase.com) (gratis
   untuk skala pemakaian kecil).
2. Di dashboard project, buka **Project Settings → Database → Connection
   string**, pilih mode **Session pooler**, lalu salin connection string-nya.
3. Di folder proyek ini, salin file `.env.example` menjadi `.env`:
   ```bash
   # macOS/Linux
   cp .env.example .env
   # Windows (PowerShell)
   copy .env.example .env
   ```
4. Buka `.env`, tempel connection string tadi ke `DATABASE_URL` (ganti bagian
   `PASSWORD` dengan password database Supabase kalian), lalu isi `SECRET_KEY`
   dengan string acak (cara cepat: jalankan
   `python -c "import secrets; print(secrets.token_hex(32))"` lalu tempel
   hasilnya).
5. Tabel-tabel (termasuk tabel `admin`, `batch_proses`, dll) akan **dibuat
   otomatis** oleh aplikasi saat pertama kali dijalankan — tidak perlu bikin
   tabel manual di Supabase.

### Membuat akun admin pertama

Sengaja tidak ada halaman "Daftar" di web (supaya tidak sembarang orang bisa
bikin akun admin). Buat akun pertama lewat terminal:

```bash
python create_admin.py
```

Ikuti instruksi di layar (isi username, nama, dan password). Skrip yang sama
juga bisa dipakai untuk reset password admin yang lupa, atau menambah admin
lain.

---

## 4. (Opsional) Membuat contoh data untuk uji coba

Karena kalian belum tentu langsung punya 380 file PDF asli untuk mencoba,
proyek ini menyediakan skrip pembuat contoh data:

```bash
python generate_sample_pdfs.py
```

Ini akan membuat 8 file PDF contoh di folder `sample_pdfs/` yang bisa
langsung dipakai untuk mencoba aplikasi dari awal sampai akhir.

---

## 5. Menjalankan aplikasi

```bash
python app.py
```

Kalau berhasil, di terminal akan muncul pesan seperti:

```
 Sistem Rekapitulasi Absensi - Daskrimti Kejati Jateng
 Buka browser: http://127.0.0.1:5000
```

Buka browser (Chrome/Edge disarankan), lalu akses:

```
http://127.0.0.1:5000
```

Aplikasi akan tampil. Untuk **menghentikan** server, kembali ke terminal
VS Code dan tekan `Ctrl+C`.

---

## 6. Cara memakai aplikasinya

1. **Unggah file** — tarik & letakkan (drag & drop) file PDF ke kotak unggah,
   atau klik **"Pilih File PDF"** (pilih banyak file sekaligus), atau klik
   **"Pilih Folder"** untuk langsung memilih seluruh folder berisi PDF.
2. Klik **"Proses Semua File"**. Progress bar akan menunjukkan file
   ke berapa yang sedang diproses, dan tabel pratinjau akan terisi
   secara langsung (live).
3. Kartu di bagian atas menunjukkan ringkasan: total file, jumlah berhasil,
   jumlah gagal/perlu dicek, dan total baris data yang berhasil dikumpulkan.
4. Jika ada file yang gagal dibaca, akan muncul di panel **"Log Berkas
   Bermasalah"** lengkap dengan alasannya — supaya kalian tidak perlu
   mengecek ulang semua file, cukup yang bermasalah saja.
5. Setelah selesai, klik **"Unduh Rekap Excel (.xlsx)"**. File akan berisi
   dua sheet: `Rekap Absensi` (data gabungan) dan `Log Kesalahan`
   (jika ada file yang gagal diproses).
6. Klik **"Mulai ulang / unggah batch baru"** untuk memproses kelompok
   file lain.

---

## 7. PENTING — Menyesuaikan pembacaan PDF dengan format ASLI

Karena contoh format PDF absensi asli dari kantor belum tersedia saat
proyek ini dibuat, logika pembacaan PDF (`extractor.py`) ditulis secara
umum berdasarkan pola absensi yang lazim (blok Nama/NIP + tabel harian).

**Sebelum dipakai untuk 380 file asli**, lakukan langkah kalibrasi berikut:

1. Ambil 2-3 contoh PDF absensi **asli** dari kantor.
2. Jalankan perintah berikut untuk melihat bagaimana teksnya terbaca:
   ```bash
   python -c "import pdfplumber; print(pdfplumber.open('contoh_asli.pdf').pages[0].extract_text())"
   ```
3. Bandingkan hasilnya dengan pola regex di `extractor.py` — cari bagian
   berkomentar `# KALIBRASI 1` dan `# KALIBRASI 2`, lalu sesuaikan kata
   kunci/label yang dicari (misalnya jika PDF asli menulis "Nomor Induk
   Pegawai" bukan "NIP", tambahkan pola barunya di situ).
4. Uji ulang dengan file asli tersebut, cek di tabel pratinjau apakah
   Nama/NIP/Tanggal/Jam sudah terbaca dengan benar.
5. Jika sudah sesuai, baru jalankan untuk seluruh 380 file.

Kalau kalian mau, tahap kalibrasi ini juga bisa dibantu lebih lanjut —
tinggal kirimkan 1-2 contoh PDF (boleh data disamarkan/dummy) untuk
disesuaikan polanya.

---

## 8. Struktur proyek

```
absensi-web/
├── app.py                    # Server web (Flask) - alur upload, proses, unduh
├── extractor.py               # Logika pembaca & pengekstrak data PDF (bagian yang dikalibrasi)
├── generate_sample_pdfs.py    # Skrip opsional pembuat contoh PDF untuk uji coba
├── requirements.txt            # Daftar paket Python yang dibutuhkan
├── templates/
│   └── index.html              # Tampilan halaman utama
├── static/
│   ├── css/style.css           # Gaya visual aplikasi
│   └── js/app.js               # Interaksi tombol, upload, progress, dsb.
├── sample_pdfs/                # Tempat contoh PDF hasil generate_sample_pdfs.py
├── uploads/                    # Tempat sementara file yang diunggah (otomatis)
└── output/                     # Tempat file Excel hasil rekap tersimpan (otomatis)
```

---

## 9. Rencana pengembangan lanjutan (setelah versi web lokal ini stabil)

Sesuai diskusi sebelumnya, setelah versi web ini terbukti bekerja dengan
baik terhadap data asli, langkah selanjutnya sesuai proposal adalah
membungkusnya menjadi **aplikasi desktop mandiri** (file yang bisa
langsung dijalankan tanpa perlu membuka terminal/VS Code), menggunakan
`pyinstaller`, supaya staf non-teknis di bidang Daskrimti bisa memakainya
dengan sekali klik setiap bulan.

---

Kalau ada error yang muncul di terminal saat menjalankan, silakan salin
pesan errornya — akan lebih mudah dibantu menelusuri penyebabnya dengan
melihat pesan tersebut.
