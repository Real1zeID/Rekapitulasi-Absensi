# -*- coding: utf-8 -*-
"""
generate_sample_pdfs.py
------------------------
Skrip BANTUAN (opsional) untuk membuat contoh file PDF "LAPORAN KEHADIRAN
PEGAWAI" dengan struktur PERSIS seperti format asli Kejaksaan Tinggi Jawa
Tengah (16 kolom tetap), supaya kalian bisa langsung mencoba alur kerja
aplikasi web sebelum memakai data 380 pegawai yang asli.

Cara pakai:
    python generate_sample_pdfs.py

Hasil tersimpan di folder sample_pdfs/, lalu tinggal di-drag & drop ke
aplikasi web untuk uji coba. Salah satu contoh (LUQMAN MAHENDRA) sengaja
dibuat punya rincian cuti, supaya fitur kolom "Cuti" di sheet rekap resmi
juga ikut teruji.
"""

import os
import random
from datetime import date, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_pdfs")
os.makedirs(OUT_DIR, exist_ok=True)

# (nama, nip, nrp, golongan, sub_unit, jabatan, rincian_cuti_atau_None)
PEGAWAI_CONTOH = [
    ("BUDI SANTOSO, S.H.", "196801011990031001", "3011001", "Jaksa Utama Muda",
     "SEKSI PENUNTUTAN", "Jaksa Ahli Utama pada Asisten Bidang Pidana Umum Kejaksaan Tinggi Jawa Tengah", None),
    ("SITI AMINAH, S.H., M.H.", "197203152001122002", "3011002", "Jaksa Madya",
     "SEKSI PENINDAKAN", "Jaksa Ahli Madya pada Asisten Bidang Pidana Militer Kejaksaan Tinggi Jawa Tengah", None),
    ("AGUS WIBOWO, S.H.", "198005202005011003", "3011003", "Jaksa Muda",
     "SEKSI PERDATA", "Jaksa Ahli Muda pada Asisten Bidang Perdata dan Tata Usaha Negara Kejaksaan Tinggi Jawa Tengah", None),
    ("DEWI LESTARI, S.H.", "199001102015022004", "3011004", "Jaksa Pratama",
     "SEKSI INTELIJEN", "Jaksa Ahli Pratama pada Asisten Bidang Intelijen Kejaksaan Tinggi Jawa Tengah", None),
    ("LUQMAN MAHENDRA, S.H.", "200404062024041002", "3011005", "Jaksa Pratama",
     "SEKSI PENINDAKAN", "Jaksa Ahli Pratama pada Asisten Bidang Pidana Militer Kejaksaan Tinggi Jawa Tengah",
     [("CUTI ALASAN PENTING", 5), ("CUTI BESAR", 3), ("CUTI PENANGGUHAN TAHUN LALU", 3)]),
]

KETERANGAN_OPSI = ["WFO", "WFO", "WFO", "WFO", "-"]
HARI_MAP = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"]

HEADER_ROW1 = ["NO.", "NAMA PEGAWAI", "NIP", "NRP", "GOL", "TANGGAL",
               "JAM KERJA", "", "JAM\nMASUK", "JAM\nKELUAR",
               "DATANG\nAWAL", "DATANG\nTELAT", "PULANG\nAWAL", "PULANG\nTELAT",
               "JML JAM\nKERJA", "KETERANGAN"]
HEADER_ROW2 = ["", "", "", "", "", "", "MASUK", "PULANG", "", "", "", "", "", "", "", ""]

COL_WIDTHS = [0.7*cm, 3.0*cm, 2.4*cm, 1.6*cm, 2.4*cm, 1.8*cm, 1.0*cm, 1.0*cm,
              1.0*cm, 1.0*cm, 1.0*cm, 1.0*cm, 1.0*cm, 1.0*cm, 1.0*cm, 1.3*cm]


def _baris_statistik(*pasangan):
    """pasangan: list of (LABEL, angka) -> '' selain kolom pertama."""
    teks = " ".join(f"{label} : {angka} Hari" for label, angka in pasangan)
    return [teks] + [""] * 15


def buat_pdf_pegawai(no, nama, nip, nrp, gol, sub_unit, jabatan, rincian_cuti, bulan_awal, jumlah_hari, path_output):
    # seed tetap berbasis NIP: memastikan data acak (jam masuk/keluar, keterangan)
    # SELALU sama untuk NIP yang sama, walau fungsi ini dipanggil berkali-kali di
    # waktu berbeda. Ini penting supaya contoh file "EKSPOR_ULANG" (dibuat sengaja
    # untuk menguji fitur deteksi duplikat) benar-benar punya data identik dengan
    # aslinya, bukan cuma NIP dan nama yang sama.
    random.seed(nip)

    doc = SimpleDocTemplate(path_output, pagesize=A4,
                             topMargin=1.2*cm, bottomMargin=1.2*cm,
                             leftMargin=0.8*cm, rightMargin=0.8*cm)
    styles = getSampleStyleSheet()
    elemen = []

    elemen.append(Paragraph("LAPORAN KEHADIRAN PEGAWAI", styles["Title"]))
    periode_akhir = bulan_awal + timedelta(days=jumlah_hari - 1)
    elemen.append(Paragraph(
        f"Periode :{bulan_awal.strftime('%d-%b-%Y')} s/d {periode_akhir.strftime('%d-%b-%Y')}",
        styles["Normal"]))
    elemen.append(Spacer(1, 6))
    elemen.append(Paragraph("KEJAKSAAN TINGGI JAWA TENGAH", styles["Heading2"]))
    elemen.append(Paragraph("Lokasi : KEJAKSAAN TINGGI JAWA TENGAH", styles["Normal"]))
    elemen.append(Paragraph("Satuan Kerja : KEJAKSAAN TINGGI JAWA TENGAH", styles["Normal"]))
    elemen.append(Paragraph("Unit Kerja : -", styles["Normal"]))
    elemen.append(Spacer(1, 10))

    data = [HEADER_ROW1, HEADER_ROW2]
    idx_subunit = len(data)
    data.append([f"SUB UNIT KERJA {sub_unit}"] + [""] * 15)
    idx_jabatan = len(data)
    data.append([f"JABATAN {jabatan}"] + [""] * 15)

    total_hari_kerja = 0
    total_terlambat = 0
    for i in range(jumlah_hari):
        tgl = bulan_awal + timedelta(days=i)
        if tgl.weekday() >= 5:
            data.append([str(no) if i == 0 else "", nama if i == 0 else "", nip if i == 0 else "",
                         nrp if i == 0 else "", gol if i == 0 else "",
                         tgl.strftime("%d-%b-%Y"), "00:00", "00:00", "-", "-", "-", "-", "-", "-", "-", ""])
            continue
        jam_masuk_jadwal, jam_pulang_jadwal = "07:30", "16:00"
        menit_masuk = random.randint(0, 50)
        jam_masuk = f"07:{menit_masuk:02d}" if menit_masuk <= 45 else f"08:{menit_masuk-45:02d}"
        telat = jam_masuk > "07:45"
        if telat:
            total_terlambat += 1
        jam_keluar = f"{random.randint(16,18):02d}:{random.randint(0,59):02d}"
        keterangan = random.choice(KETERANGAN_OPSI)
        total_hari_kerja += 1
        data.append([
            str(no) if i == 0 else "", nama if i == 0 else "", nip if i == 0 else "",
            nrp if i == 0 else "", gol if i == 0 else "",
            tgl.strftime("%d-%b-%Y"), jam_masuk_jadwal, jam_pulang_jadwal,
            jam_masuk, jam_keluar, "23:30", "-" if not telat else "-", "-", "13:30",
            "13:30", keterangan,
        ])

    total_cuti = sum(j for _, j in rincian_cuti) if rincian_cuti else 0
    data.append(_baris_statistik(
        ("TERLAMBAT", total_terlambat), ("PULANG CEPAT", 0), ("TIDAK ABSEN DATANG", 0),
        ("TIDAK ABSEN PULANG", 0), ("IZIN", 0), ("TOTAL HARI KERJA", total_hari_kerja),
    ))
    data.append(_baris_statistik(
        ("ALPHA", 0), ("SAKIT", 0), ("DINAS LUAR", 0), ("LEPAS PIKET", 0),
        ("TUGAS BELAJAR", 0), ("TOTAL CUTI", total_cuti),
    ))
    if rincian_cuti:
        data.append(_baris_statistik(*rincian_cuti))

    # baris statistik (3 baris terakhir sebelum ini ditambahkan) harus digabung
    # jadi satu sel utuh (span), supaya tidak terpotong garis kolom saat dibaca ulang
    idx_statistik_awal = len(data) - (3 if rincian_cuti else 2)

    tabel = Table(data, colWidths=COL_WIDTHS, repeatRows=2)
    gaya = [
        ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#1F4E37")),
        ("TEXTCOLOR", (0, 0), (-1, 1), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 6.2),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for r in range(idx_statistik_awal, len(data)):
        gaya.append(("SPAN", (0, r), (-1, r)))
        gaya.append(("ALIGN", (0, r), (-1, r), "LEFT"))
        gaya.append(("FONTSIZE", (0, r), (-1, r), 5.8))
    for r in (idx_subunit, idx_jabatan):
        gaya.append(("SPAN", (0, r), (-1, r)))
        gaya.append(("ALIGN", (0, r), (-1, r), "LEFT"))
        gaya.append(("FONTSIZE", (0, r), (-1, r), 6.2))
    tabel.setStyle(TableStyle(gaya))
    elemen.append(tabel)
    doc.build(elemen)


def main():
    bulan_awal = date(2026, 6, 20)
    for i, item in enumerate(PEGAWAI_CONTOH, start=1):
        nama, nip, nrp, gol, sub_unit, jabatan = item[:6]
        rincian_cuti = item[6] if len(item) > 6 else None
        nama_file = f"absensi_{i:03d}_{nama.split(',')[0].replace(' ', '_')}.pdf"
        path_output = os.path.join(OUT_DIR, nama_file)
        buat_pdf_pegawai(i, nama, nip, nrp, gol, sub_unit, jabatan, rincian_cuti, bulan_awal, 20, path_output)
        tanda = "  (dengan rincian cuti)" if rincian_cuti else ""
        print(f"  dibuat: {nama_file}{tanda}")

    # contoh file DUPLIKAT (data sama, nama file & isi byte berbeda) - untuk
    # mencoba fitur deteksi duplikat tanpa perlu menunggu kasus nyata
    if PEGAWAI_CONTOH:
        nama, nip, nrp, gol, sub_unit, jabatan = PEGAWAI_CONTOH[0][:6]
        rincian_cuti = PEGAWAI_CONTOH[0][6] if len(PEGAWAI_CONTOH[0]) > 6 else None
        nama_file_dup = f"absensi_001_{nama.split(',')[0].replace(' ', '_')}_EKSPOR_ULANG.pdf"
        buat_pdf_pegawai(1, nama, nip, nrp, gol, sub_unit, jabatan, rincian_cuti, bulan_awal, 20,
                          os.path.join(OUT_DIR, nama_file_dup))
        print(f"  dibuat: {nama_file_dup}  (contoh duplikat - untuk uji fitur deteksi duplikat)")

    print(f"\nSelesai. Contoh PDF tersimpan di: {OUT_DIR}")
    print("Silakan drag & drop folder 'sample_pdfs' ini ke aplikasi web untuk uji coba.")
    print("Coba unggah 'absensi_001_..._EKSPOR_ULANG.pdf' bersama file lain untuk melihat")
    print("bagaimana file itu otomatis terdeteksi sebagai duplikat di Log Berkas Bermasalah.")


if __name__ == "__main__":
    main()
