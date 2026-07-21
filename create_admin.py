# -*- coding: utf-8 -*-
"""
create_admin.py
----------------
Skrip untuk membuat (atau reset password) akun admin lewat terminal.
Sengaja TIDAK ada halaman "Daftar" di web supaya akun admin hanya bisa
dibuat oleh orang yang punya akses ke server/komputer ini.

Cara pakai (pastikan venv sudah aktif & .env sudah diisi DATABASE_URL):

    python create_admin.py

Lalu ikuti instruksi di layar (isi username, nama, dan password).
"""

import getpass

from dotenv import load_dotenv
load_dotenv()  # baca .env (DATABASE_URL, dll) SEBELUM import db - kalau tidak, db.py akan
                # memakai nilai default (localhost) dan gagal konek ke Supabase

from db import init_db, get_session, Admin
from auth import buat_hash_password


def main():
    print("=" * 60)
    print(" Buat / reset akun admin - Sistem Rekapitulasi Absensi")
    print("=" * 60)

    init_db()  # pastikan tabel (termasuk tabel admin) sudah ada

    username = input("Username admin: ").strip()
    if not username:
        print("Username tidak boleh kosong. Dibatalkan.")
        return

    nama_lengkap = input("Nama lengkap (opsional): ").strip()

    password = getpass.getpass("Password baru: ")
    password_konfirmasi = getpass.getpass("Ulangi password: ")
    if password != password_konfirmasi:
        print("Password tidak sama. Dibatalkan.")
        return
    if len(password) < 8:
        print("Password minimal 8 karakter. Dibatalkan.")
        return

    session = get_session()
    try:
        admin = session.query(Admin).filter(Admin.username == username).first()
        if admin:
            admin.password_hash = buat_hash_password(password)
            if nama_lengkap:
                admin.nama_lengkap = nama_lengkap
            admin.aktif = True
            session.commit()
            print(f"\nPassword untuk admin '{username}' berhasil di-reset.")
        else:
            admin = Admin(
                username=username,
                password_hash=buat_hash_password(password),
                nama_lengkap=nama_lengkap,
                aktif=True,
            )
            session.add(admin)
            session.commit()
            print(f"\nAkun admin '{username}' berhasil dibuat.")
    finally:
        session.close()


if __name__ == "__main__":
    main()