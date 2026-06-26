from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

DB_FILE = "database_lostfound.db"

# Fungsi untuk membuat koneksi ke SQLite database
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    # Row_factory membuat data yang diambil berbentuk seperti dictionary/key-value
    conn.row_factory = sqlite3.Row
    return conn

# Fungsi untuk inisialisasi database dan tabel saat aplikasi pertama berjalan
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS barang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipe TEXT NOT NULL,
            nama TEXT NOT NULL,
            kategori TEXT NOT NULL,
            lokasi TEXT NOT NULL,
            deskripsi TEXT,
            kontak TEXT,
            tanggal TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Jalankan inisialisasi database
init_db()

@app.route('/', methods=['GET', 'POST'])
def welcome():
    pesan_error = None
    if request.method == 'POST':
        password_input = request.form.get('password')
        
        if password_input == 'admin123': 
            return redirect(url_for('index', role='admin'))
        else:
            pesan_error = "Kata sandi Admin salah! Silakan coba lagi."
            
    return render_template('welcome.html', error=pesan_error)

@app.route('/index')
def index():
    status_tab = request.args.get('status', 'all')
    kategori_filter = request.args.get('kategori', '')
    pencarian = request.args.get('search', '').lower()
    role_aktif = request.args.get('role', 'guest')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Menghitung Statistik Secara Real-time langsung dari Database SQL
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Lost'")
    total_hilang = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Found'")
    total_ditemukan = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Done'")
    total_selesai = cursor.fetchone()[0]
    
    # 2. Menyusun Query SQL dasar untuk memfilter data barang
    query = "SELECT * FROM barang WHERE 1=1"
    params = []
    
    if status_tab == 'Lost':
        query += " AND tipe = 'Lost'"
    elif status_tab == 'Found':
        query += " AND tipe = 'Found'"
    elif status_tab == 'Done':
        query += " AND tipe = 'Done'"
    else:
        query += " AND tipe != 'Done'"
        
    if kategori_filter:
        query += " AND kategori = ?"
        params.append(kategori_filter)
        
    if pencarian:
        query += " AND (LOWER(nama) LIKE ? OR LOWER(deskripsi) LIKE ?)"
        params.append(f"%{pencarian}%")
        params.append(f"%{pencarian}%")
        
    # Urutkan data berdasarkan ID paling baru dimasukkan
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Konversi hasil SQLite Row ke bentuk list dictionary biasa agar tidak merusak template HTML kamu
    hasil_filter = [dict(row) for row in rows]
        
    return render_template('index.html', 
                           barang=hasil_filter, 
                           kategori_aktif=kategori_filter, 
                           cari=pencarian, 
                           tab_aktif=status_tab,
                           hilang=total_hilang,
                           ditemukan=total_ditemukan,
                           selesai=total_selesai,
                           role=role_aktif)


# ==============================================================================
# 3. PROSES MENGUBAH STATUS BARANG (MENGGUNAKAN UPDATE SQL)
# ==============================================================================
@app.route('/selesai/<int:barang_id>')
def selesai(barang_id):
    role_aktif = request.args.get('role', 'guest')
    
    if role_aktif == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE barang SET tipe = 'Done' WHERE id = ?", (barang_id,))
        conn.commit()
        conn.close()
                
    return redirect(url_for('index', status=request.args.get('status', 'all'), role=role_aktif))


# ==============================================================================
# 4. PROSES HAPUS BARANG (MENGGUNAKAN DELETE SQL)
# ==============================================================================
@app.route('/hapus/<int:barang_id>')
def hapus(barang_id):
    role_aktif = request.args.get('role', 'guest')
    
    if role_aktif == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM barang WHERE id = ?", (barang_id,))
        conn.commit()
        conn.close()
        
    return redirect(url_for('index', status=request.args.get('status', 'all'), role=role_aktif))


# ==============================================================================
# 5. HALAMAN LAPOR BARANG BARU (MENGGUNAKAN INSERT INTO SQL - AUTO INCREMENT ID)
# ==============================================================================
@app.route('/laporkan', methods=['GET', 'POST'])
def laporkan():
    role_aktif = request.args.get('role', 'guest')
    
    if request.method == 'POST':
        # Ambil data kiriman dari formulir laporkan.html
        tipe = request.form.get('tipe')
        nama = request.form.get('nama')
        kategori = request.form.get('kategori')
        lokasi = request.form.get('lokasi')
        deskripsi = request.form.get('deskripsi')
        kontak = request.form.get('kontak')
        tanggal_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Masukkan data ke SQLite (ID otomatis terisi secara auto-increment karena setingan tabel)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO barang (tipe, nama, kategori, lokasi, deskripsi, kontak, tanggal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (tipe, nama, kategori, lokasi, deskripsi, kontak, tanggal_sekarang))
        conn.commit()
        conn.close()

        # Lempar kembali ke halaman utama dashboard dengan role yang sama
        return redirect(url_for('index', role=role_aktif))

    return render_template('laporkan.html', role=role_aktif)


# ==============================================================================
# RUNNER SERVER UTAMA
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True)