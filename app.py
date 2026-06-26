from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

DB_FILE = "database_lostfound.db"

# ==============================================================================
# FITUR 1: PROFANITY FILTER (BLACKLIST KATA KASAR)
# ==============================================================================
# Kamu bisa bebas menambahkan kata-kata kasar lokal/daerah lainnya di dalam list ini
KATA_KASAR_BLACKLIST = ['anjing', 'babi', 'bodoh', 'tolol', 'bangsat', 'puki', 'laso'] 

def mengandung_kata_kasar(teks):
    if not teks:
        return False
    teks_lower = teks.lower()
    for kata in KATA_KASAR_BLACKLIST:
        if kata in teks_lower:
            return True
    return False

# ==============================================================================
# UTILITAS DATABASE
# ==============================================================================
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Membuat tabel jika belum ada (tipe default nanti bisa diisi 'Pending', 'Lost', 'Found', 'Done')
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

init_db()

# ==============================================================================
# ROUTES UTAMA
# ==============================================================================
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
    
    # Menghitung Statistik (Hanya menghitung yang statusnya disetujui / bukan 'Pending')
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Lost'")
    total_hilang = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Found'")
    total_ditemukan = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Done'")
    total_selesai = cursor.fetchone()[0]
    
    # Hitung juga jumlah antrean laporan khusus untuk Admin
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe LIKE 'Pending_%'")
    total_pending = cursor.fetchone()[0]
    
    # Menyusun Query SQL dasar (GUEST TIDAK BISA MELIHAT DATA PENDING)
    query = "SELECT * FROM barang WHERE 1=1"
    params = []
    
    if status_tab == 'Lost':
        query += " AND tipe = 'Lost'"
    elif status_tab == 'Found':
        query += " AND tipe = 'Found'"
    elif status_tab == 'Done':
        query += " AND tipe = 'Done'"
    elif status_tab == 'Pending' and role_aktif == 'admin':
        # Tab khusus admin untuk melihat antrean persetujuan
        query += " AND tipe LIKE 'Pending_%'"
    else:
        # Tampilan default halaman utama (tidak memunculkan data pending & done)
        query += " AND tipe NOT LIKE 'Pending_%' AND tipe != 'Done'"
        
    if kategori_filter:
        query += " AND kategori = ?"
        params.append(kategori_filter)
        
    if pencarian:
        query += " AND (LOWER(nama) LIKE ? OR LOWER(deskripsi) LIKE ?)"
        params.append(f"%{pencarian}%")
        params.append(f"%{pencarian}%")
        
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    hasil_filter = [dict(row) for row in rows]
        
    return render_template('index.html', 
                           barang=hasil_filter, 
                           kategori_aktif=kategori_filter, 
                           cari=pencarian, 
                           tab_aktif=status_tab,
                           hilang=total_hilang,
                           ditemukan=total_ditemukan,
                           selesai=total_selesai,
                           pending_count=total_pending, # Kirim variabel jumlah antrean ke HTML
                           role=role_aktif)

# ==============================================================================
# FITUR 2: AKSI APPROVAL ADMIN (SETUJUI DAN TOLAK)
# ==============================================================================
@app.route('/setujui/<int:barang_id>')
def setujui(barang_id):
    role_aktif = request.args.get('role', 'guest')
    if role_aktif == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor()
        # Ambil data tipe aslinya (Pending_Lost atau Pending_Found)
        cursor.execute("SELECT tipe FROM barang WHERE id = ?", (barang_id,))
        row = cursor.fetchone()
        if row:
            tipe_asli = row['tipe'].split('_')[1] # Mengambil kata setelah 'Pending_'
            # Update tipe menjadi murni 'Lost' atau 'Found' agar tayang ke publik
            cursor.execute("UPDATE barang SET tipe = ? WHERE id = ?", (tipe_asli, barang_id))
            conn.commit()
        conn.close()
    return redirect(url_for('index', status='Pending', role=role_aktif))

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

@app.route('/hapus/<int:barang_id>')
def hapus(barang_id):
    role_aktif = request.args.get('role', 'guest')
    if role_aktif == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM barang WHERE id = ?", (barang_id,))
        conn.commit()
        conn.close()
    # Mengembalikan admin ke tab asal saat dia mengklik hapus/tolak
    return redirect(url_for('index', status=request.args.get('status', 'all'), role=role_aktif))

# ==============================================================================
# HALAMAN LAPOR BARANG BARU (DENGAN FILTER KATA KASAR & SAVE SEBAGAI PENDING)
# ==============================================================================
@app.route('/laporkan', methods=['GET', 'POST'])
def laporkan():
    role_aktif = request.args.get('role', 'guest')
    pesan_error = None
    
    if request.method == 'POST':
        tipe = request.form.get('tipe')
        nama = request.form.get('nama')
        kategori = request.form.get('kategori')
        lokasi = request.form.get('lokasi')
        deskripsi = request.form.get('deskripsi')
        kontak = request.form.get('kontak')
        tanggal_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Jalankan Fitur 1: Cek Kata Kasar
        if mengandung_kata_kasar(nama) or mengandung_kata_kasar(lokasi) or mengandung_kata_kasar(deskripsi):
            pesan_error = "Laporan ditolak! Harap tidak menggunakan kata-kata kasar/sensitif."
            return render_template('laporkan.html', error=pesan_error, role=role_aktif)

        # Jalankan Fitur 2: Ubah status menjadi Pending sebelum disimpan (misal: Pending_Lost)
        status_pending = f"Pending_{tipe}"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO barang (tipe, nama, kategori, lokasi, deskripsi, kontak, tanggal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (status_pending, nama, kategori, lokasi, deskripsi, kontak, tanggal_sekarang))
        conn.commit()
        conn.close()

        # Setelah sukses melapor, arahkan kembali ke index
        return redirect(url_for('index', role=role_aktif))

    return render_template('laporkan.html', role=role_aktif, error=pesan_error)

if __name__ == '__main__':
    app.run(debug=True)