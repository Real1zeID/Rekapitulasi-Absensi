# -*- coding: utf-8 -*-
"""
db.py
-----
Lapisan database untuk Sistem Rekapitulasi Absensi.
Menggunakan SQLAlchemy ORM + driver psycopg2, terhubung ke Supabase
(PostgreSQL terkelola di cloud) sebagai pengganti MySQL lokal (XAMPP/Laragon).

Konfigurasi koneksi diambil dari environment variable. Cara termudah:
ambil "Connection string" dari Supabase (Project Settings -> Database ->
Connection string -> pilih mode "Session pooler" atau "Transaction pooler"
untuk koneksi yang stabil dari luar jaringan Supabase), lalu isi sebagai
satu variabel:

    DATABASE_URL=postgresql+psycopg2://postgres.xxxxx:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

Kalau DATABASE_URL tidak diisi, kode di bawah akan menyusunnya dari
variabel terpisah (opsional, kalau lebih suka begitu):

    DB_HOST      contoh: aws-0-ap-southeast-1.pooler.supabase.com
    DB_PORT      default: 5432
    DB_USER      contoh: postgres.xxxxxxxxxxxx
    DB_PASSWORD  password database Supabase kalian
    DB_NAME      default: postgres

Simpan nilai-nilai ini di file `.env` (JANGAN pernah di-commit ke git -
sudah ada di .gitignore) dan muat dengan `python-dotenv` di app.py.

Tabel akan dibuat otomatis oleh SQLAlchemy saat app pertama kali start
(lihat init_db() yang dipanggil dari app.py) - tidak perlu bikin tabel
manual lewat SQL Editor Supabase.
"""

import os
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DB_HOST = os.environ.get("DB_HOST", "")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")

DATABASE_URL = os.environ.get("DATABASE_URL") or (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# pool_pre_ping penting untuk koneksi cloud seperti Supabase - mendeteksi
# koneksi yang sudah putus (mis. idle terlalu lama) dan membuat ulang,
# supaya tidak muncul error "server closed the connection unexpectedly".
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Admin(Base):
    """Akun admin untuk login ke aplikasi. Password disimpan sebagai hash
    (werkzeug.security), bukan teks biasa. Dibuat lewat skrip create_admin.py,
    bukan lewat form pendaftaran publik - sengaja tidak ada halaman "Daftar"
    supaya hanya admin yang sudah diberi akses lewat CLI/server yang bisa masuk."""
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nama_lengkap = Column(String(150), default="")
    aktif = Column(Boolean, default=True)
    dibuat_pada = Column(DateTime, default=datetime.now)
    login_terakhir = Column(DateTime, nullable=True)


class BatchProses(Base):
    """Satu baris = satu kali proses upload+ekstraksi (satu klik 'Proses')."""
    __tablename__ = "batch_proses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bidang_override = Column(String(255), default="")
    total_file = Column(Integer, default=0)
    berhasil = Column(Integer, default=0)
    gagal = Column(Integer, default=0)
    mulai = Column(DateTime, default=datetime.now)
    selesai = Column(DateTime, nullable=True)
    dibuat_oleh = Column(String(80), default="")  # username admin yang menjalankan batch ini

    baris_harian = relationship(
        "AbsensiHarian", back_populates="batch", cascade="all, delete-orphan"
    )
    ringkasan = relationship(
        "RingkasanKehadiran", back_populates="batch", cascade="all, delete-orphan"
    )


class AbsensiHarian(Base):
    """Satu baris = satu pegawai pada satu tanggal (hasil ekstrak_pdf -> rows)."""
    __tablename__ = "absensi_harian"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batch_proses.id"), nullable=False)

    nama = Column(String(150))
    nip = Column(String(50))
    nrp = Column(String(50))
    golongan = Column(String(20))
    sub_unit_kerja = Column(String(255))
    jabatan = Column(String(150))
    tanggal = Column(String(20))  # disimpan sebagai teks dd/mm/yyyy, sesuai format asal
    jadwal_masuk = Column(String(10))
    jadwal_pulang = Column(String(10))
    jam_masuk = Column(String(10))
    jam_keluar = Column(String(10))
    datang_awal = Column(String(10))
    datang_telat = Column(String(10))
    pulang_awal = Column(String(10))
    pulang_telat = Column(String(10))
    jumlah_jam_kerja = Column(String(10))
    keterangan = Column(String(100))
    sumber_file = Column(String(255))

    batch = relationship("BatchProses", back_populates="baris_harian")

    @classmethod
    def from_row_dict(cls, d, batch_id):
        """Konversi dict hasil ekstrak_pdf() (rows) -> objek model."""
        return cls(
            batch_id=batch_id,
            nama=d.get("Nama"),
            nip=d.get("NIP"),
            nrp=d.get("NRP"),
            golongan=d.get("Golongan"),
            sub_unit_kerja=d.get("Sub Unit Kerja"),
            jabatan=d.get("Jabatan"),
            tanggal=d.get("Tanggal"),
            jadwal_masuk=d.get("Jadwal Masuk"),
            jadwal_pulang=d.get("Jadwal Pulang"),
            jam_masuk=d.get("Jam Masuk"),
            jam_keluar=d.get("Jam Keluar"),
            datang_awal=d.get("Datang Awal"),
            datang_telat=d.get("Datang Telat"),
            pulang_awal=d.get("Pulang Awal"),
            pulang_telat=d.get("Pulang Telat"),
            jumlah_jam_kerja=d.get("Jumlah Jam Kerja"),
            keterangan=d.get("Keterangan"),
            sumber_file=d.get("Sumber File"),
        )


class RingkasanKehadiran(Base):
    """Satu baris = satu pegawai, rekap statistik (hasil ekstrak_pdf -> ringkasan)."""
    __tablename__ = "ringkasan_kehadiran"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batch_proses.id"), nullable=False)

    nama = Column(String(150))
    nip = Column(String(50))
    nrp = Column(String(50))
    golongan = Column(String(20))
    terlambat = Column(String(10))
    pulang_cepat = Column(String(10))
    tidak_absen_datang = Column(String(10))
    tidak_absen_pulang = Column(String(10))
    izin = Column(String(10))
    alpha = Column(String(10))
    sakit = Column(String(10))
    dinas_luar = Column(String(10))
    lepas_piket = Column(String(10))
    tugas_belajar = Column(String(10))
    total_cuti = Column(String(10))
    rincian_cuti = Column(Text)
    total_hari_kerja = Column(String(10))
    sumber_file = Column(String(255))
    sub_unit = Column(String(255))
    jabatan = Column(String(150))

    batch = relationship("BatchProses", back_populates="ringkasan")

    @classmethod
    def from_ringkasan_dict(cls, d, batch_id):
        """Konversi dict hasil ekstrak_pdf() (ringkasan) -> objek model."""
        return cls(
            batch_id=batch_id,
            nama=d.get("Nama"),
            nip=d.get("NIP"),
            nrp=d.get("NRP"),
            golongan=d.get("Golongan"),
            terlambat=d.get("Terlambat (Hari)"),
            pulang_cepat=d.get("Pulang Cepat (Hari)"),
            tidak_absen_datang=d.get("Tidak Absen Datang (Hari)"),
            tidak_absen_pulang=d.get("Tidak Absen Pulang (Hari)"),
            izin=d.get("Izin (Hari)"),
            alpha=d.get("Alpha (Hari)"),
            sakit=d.get("Sakit (Hari)"),
            dinas_luar=d.get("Dinas Luar (Hari)"),
            lepas_piket=d.get("Lepas Piket (Hari)"),
            tugas_belajar=d.get("Tugas Belajar (Hari)"),
            total_cuti=d.get("Total Cuti (Hari)"),
            rincian_cuti=d.get("Rincian Cuti"),
            total_hari_kerja=d.get("Total Hari Kerja"),
            sumber_file=d.get("Sumber File"),
            sub_unit=d.get("_sub_unit"),
            jabatan=d.get("_jabatan"),
        )


class FileHashTerproses(Base):
    """Menyimpan hash (sha256) setiap file PDF yang sudah pernah diproses,
    supaya deteksi 'file dengan isi persis sama' tetap berjalan walaupun
    app di-restart (tidak hanya mengandalkan memori STATE)."""
    __tablename__ = "file_hash_terproses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_hash = Column(String(64), unique=True, index=True, nullable=False)
    nama_file = Column(String(255))
    batch_id = Column(Integer, ForeignKey("batch_proses.id"), nullable=True)
    dibuat_pada = Column(DateTime, default=datetime.now)


class SignaturePegawaiTerproses(Base):
    """Menyimpan signature (NIP + rincian harian) setiap pegawai yang sudah
    pernah masuk ke rekap, supaya deteksi 'data sama, file beda' tetap
    berjalan walaupun app di-restart."""
    __tablename__ = "signature_pegawai_terproses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signature = Column(String(64), unique=True, index=True, nullable=False)
    nip = Column(String(50))
    nama_file = Column(String(255))
    batch_id = Column(Integer, ForeignKey("batch_proses.id"), nullable=True)
    dibuat_pada = Column(DateTime, default=datetime.now)


def init_db():
    """Buat semua tabel jika belum ada. Dipanggil sekali saat app start."""
    Base.metadata.create_all(bind=engine)


def muat_dedup_index():
    """Baca seluruh file_hash & signature yang sudah pernah tersimpan di
    Supabase, dikembalikan sebagai dict siap-pakai untuk STATE di app.py.
    Dipanggil sekali saat app.py start, supaya deteksi duplikat tetap
    'ingat' walaupun proses Python-nya baru saja di-restart."""
    session = get_session()
    try:
        file_hash_index = {
            row.file_hash: row.nama_file for row in session.query(FileHashTerproses).all()
        }
        content_signature_index = {
            row.signature: row.nama_file for row in session.query(SignaturePegawaiTerproses).all()
        }
        return file_hash_index, content_signature_index
    finally:
        session.close()


def get_session():
    """Buka session baru. Selalu tutup manual (session.close()) atau pakai 'with'."""
    return SessionLocal()
