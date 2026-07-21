# -*- coding: utf-8 -*-
"""
auth.py
-------
Login admin sederhana - TIDAK pakai Supabase Auth, murni tabel `admin`
sendiri di database (lihat db.py) + session cookie bawaan Flask.

Sengaja dibuat simpel:
- Tidak ada halaman "Daftar akun" publik. Akun admin dibuat lewat
  create_admin.py (dijalankan dari terminal oleh yang mengelola server).
- Password disimpan sebagai hash (werkzeug.security.generate_password_hash),
  bukan teks biasa.
- Status login disimpan di session cookie Flask (ditandatangani server
  dengan SECRET_KEY, tidak bisa dipalsukan pengguna tanpa tahu kuncinya).

Dipakai di app.py dengan menambahkan @login_required di atas setiap
route yang hanya boleh diakses admin.
"""

from functools import wraps
from datetime import datetime

from flask import session, redirect, url_for, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_session, Admin


def buat_hash_password(password_polos):
    """Ubah password teks biasa menjadi hash aman untuk disimpan di DB."""
    return generate_password_hash(password_polos)


def cek_login(username, password_polos):
    """Cek username+password ke tabel admin.
    Return objek Admin kalau cocok & aktif, None kalau tidak."""
    session_db = get_session()
    try:
        admin = session_db.query(Admin).filter(
            Admin.username == username.strip()
        ).first()
        if not admin or not admin.aktif:
            return None
        if not check_password_hash(admin.password_hash, password_polos):
            return None
        admin.login_terakhir = datetime.now()
        session_db.commit()
        return {"id": admin.id, "username": admin.username, "nama_lengkap": admin.nama_lengkap}
    finally:
        session_db.close()


def login_required(view_func):
    """Decorator: taruh di atas route Flask yang hanya boleh diakses admin
    yang sudah login. Kalau belum login:
    - request biasa (buka halaman)  -> diarahkan ke /login
    - request API/JSON (fetch dari JS) -> balas 401 JSON, bukan redirect,
      supaya JavaScript di frontend bisa menangani dengan rapi."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_username"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "pesan": "Sesi login berakhir, silakan login ulang."}), 401
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapper
