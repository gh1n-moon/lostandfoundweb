from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "kunci_rahasia_lostfound_unipol"

# Tentukan tempat penyimpanan folder foto (masuk ke static/uploads)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Pastikan folder 'static/uploads' otomatis terbuat jika belum ada
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = "database_lostfound.db"

# ==============================================================================
# FITUR 1: PROFANITY FILTER (BLACKLIST KATA KASAR)
# ==============================================================================
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
# UTILITAS DATABASE (DENGAN RESTRUKTURISASI TABEL KATEGORI)
# ==============================================================================
def get_db_connection():
    # Sesuaikan nama databasemu yang aktif (database.db atau database_lostfound.db)
    conn = sqlite3.connect('database.db') 
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    
    # 1. Otomatis tambah kolom foto ke tabel barang jika belum ada
    try:
        cursor.execute("ALTER TABLE barang ADD COLUMN foto TEXT DEFAULT 'default.jpg';")
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
    # 2. OTOMATIS BUAT TABEL KLAIM BARU JIKALAU BELUM ADA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS klaim (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barang_id INTEGER,
            nama_klaim TEXT NOT NULL,
            nim_klaim TEXT NOT NULL,
            wa_klaim TEXT NOT NULL,
            bukti_detail TEXT NOT NULL,
            tanggal_klaim TEXT NOT NULL,
            FOREIGN KEY (barang_id) REFERENCES barang (id)
        )
    ''')
    conn.commit()
        
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Membuat tabel barang jika belum ada
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
    
    # 2. TABEL BARU: Membuat tabel daftar kategori dinamis
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daftar_kategori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_kategori TEXT NOT NULL UNIQUE
        )
    ''')
    
    # 3. Isi kategori bawaan awal (default) jika tabel kategori masih kosong melompong
    cursor.execute("SELECT COUNT(*) FROM daftar_kategori")
    if cursor.fetchone()[0] == 0:
        kategori_awal = [
            ('Dokumen/Kartu',), 
            ('Perangkat Elektronik',), 
            ('Kunci Kendaraan',), 
            ('Dompet/Uang',), 
            ('Lainnya',)
        ]
        cursor.executemany("INSERT INTO daftar_kategori (nama_kategori) VALUES (?)", kategori_awal)
        
    conn.commit()
    conn.close()

# Jalankan inisialisasi database saat aplikasi start
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
        query += " AND tipe LIKE 'Pending_%'"
    else:
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
    hasil_filter = [dict(row) for row in rows]
    
    # AMBIL DATA DARI TABEL KATEGORI: Untuk dioper ke dropdown filter halaman utama
    cursor.execute("SELECT * FROM daftar_kategori ORDER BY id ASC")
    kategori_db = cursor.fetchall()
    
    conn.close()
        
    return render_template('index.html', 
                           barang=hasil_filter, 
                           kategori_aktif=kategori_filter, 
                           cari=pencarian, 
                           tab_aktif=status_tab,
                           hilang=total_hilang,
                           ditemukan=total_ditemukan,
                           selesai=total_selesai,
                           pending_count=total_pending,
                           kategori_list=kategori_db, # Dikirimkan ke HTML
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
        cursor.execute("SELECT tipe FROM barang WHERE id = ?", (barang_id,))
        row = cursor.fetchone()
        if row:
            tipe_asli = row['tipe'].split('_')[1] 
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
    return redirect(url_for('index', status=request.args.get('status', 'all'), role=role_aktif))

# ==============================================================================
# HALAMAN LAPOR BARANG BARU (DENGAN DROP-DOWN KATEGORI DINAMIS)
# ==============================================================================
@app.route('/laporkan', methods=['GET', 'POST'])
def laporkan():
    role_aktif = request.args.get('role', 'guest')
    pesan_error = None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        tipe = request.form.get('tipe')
        nama = request.form.get('nama')
        kategori = request.form.get('kategori')
        lokasi = request.form.get('lokasi')
        deskripsi = request.form.get('deskripsi')
        kontak = request.form.get('kontak')
        tanggal_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Ambil list kategori untuk render ulang jika terjadi error filter kata kasar
        cursor.execute("SELECT * FROM daftar_kategori ORDER BY id ASC")
        kategori_db = cursor.fetchall()

        if mengandung_kata_kasar(nama) or mengandung_kata_kasar(lokasi) or mengandung_kata_kasar(deskripsi):
            pesan_error = "Laporan ditolak! Harap tidak menggunakan kata-kata kasar/sensitif."
            conn.close()
            return render_template('laporkan.html', error=pesan_error, role=role_aktif, kategori_list=kategori_db)

        # =======================================================
        # AWAL LOGIKA UNGGAH FOTO BARANG (LANGKAH KEDUA)
        # =======================================================
        file_foto = request.files.get('foto_barang')
        if file_foto and file_foto.filename != '':
            # Amankan nama file (misal: "kunci motor.jpg" -> "kunci_motor.jpg")
            filename = secure_filename(file_foto.filename)
            # Tentukan jalur penyimpanan ke static/uploads/nama_file.jpg
            jalur_simpan = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            # Simpan file fisiknya ke folder server
            file_foto.save(jalur_simpan)
        else:
            # Jika user tidak upload foto, otomatis pakai gambar bawaan
            filename = 'default.jpg'
        # =======================================================
        # AKHIR LOGIKA UNGGAH FOTO BARANG
        # =======================================================

        status_pending = f"Pending_{tipe}"

        # MENAMBAHKAN KOLOM 'foto' DAN VARIABEL 'filename' PADA QUERY INSERT
        cursor.execute('''
            INSERT INTO barang (tipe, nama, kategori, lokasi, deskripsi, kontak, tanggal, foto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (status_pending, nama, kategori, lokasi, deskripsi, kontak, tanggal_sekarang, filename))
        
        conn.commit()
        conn.close()
        
        flash("Laporan Anda berhasil dikirim! Laporan sedang berada dalam antrean peninjauan Admin sebelum diterbitkan ke publik.", "sukses_pending")
        return redirect(url_for('index', role=role_aktif))

    # Pengambilan data kategori untuk metode GET (tampilan awal form)
    cursor.execute("SELECT * FROM daftar_kategori ORDER BY id ASC")
    kategori_db = cursor.fetchall()
    conn.close()
    
    return render_template('laporkan.html', role=role_aktif, error=pesan_error, kategori_list=kategori_db)

@app.route('/klaim/<int:barang_id>', methods=['GET', 'POST'])
def klaim(barang_id):
    role_aktif = request.args.get('role', 'guest')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ambil data barang yang mau diklaim
    cursor.execute("SELECT * FROM barang WHERE id = ?", (barang_id,))
    item = cursor.fetchone()
    
    if request.method == 'POST':
        nama_klaim = request.form.get('nama_klaim')
        nim_klaim = request.form.get('nim_klaim')
        wa_klaim = request.form.get('wa_klaim')
        bukti_detail = request.form.get('bukti_detail')
        tanggal_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 1. Masukkan data pengklaim ke tabel klaim
        cursor.execute('''
            INSERT INTO klaim (barang_id, nama_klaim, nim_klaim, wa_klaim, bukti_detail, tanggal_klaim)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (barang_id, nama_klaim, nim_klaim, wa_klaim, bukti_detail, tanggal_sekarang))
        
        # 2. Ubah tipe/status barang menjadi 'Dalam_Proses_Klaim' agar terkunci di halaman utama
        # Kita deteksi apakah asal barangnya Lost atau Found agar admin tahu
        status_baru = "Dalam_Proses_Klaim"
        cursor.execute("UPDATE barang SET tipe = ? WHERE id = ?", (status_baru, barang_id))
        
        conn.commit()
        conn.close()
        
        flash("Permintaan klaim berhasil dikirim! Admin akan segera meninjau bukti Anda dan menghubungi Anda lewat WhatsApp.", "sukses_pending")
        return redirect(url_for('index', role=role_aktif))
        
    conn.close()
    return render_template('klaim.html', item=item, role=role_aktif)

# ==============================================================================
# ROUTE BARU: MANAGEMENT KATEGORI (KHUSUS ADMIN)
# ==============================================================================
@app.route('/admin/kategori', methods=['GET', 'POST'])
def kelola_kategori():
    role_aktif = request.args.get('role', 'guest')
    if role_aktif != 'admin':
        return redirect(url_for('index', role=role_aktif))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    pesan_error = None

    if request.method == 'POST':
        nama_baru = request.form.get('nama_kategori_baru').strip()
        if nama_baru:
            try:
                cursor.execute("INSERT INTO daftar_kategori (nama_kategori) VALUES (?)", (nama_baru,))
                conn.commit()
            except sqlite3.IntegrityError:
                pesan_error = "Kategori tersebut sudah terdaftar!"
        else:
            pesan_error = "Nama kategori tidak boleh dikosongkan."

    cursor.execute("SELECT * FROM daftar_kategori ORDER BY id ASC")
    kategori_db = cursor.fetchall()
    conn.close()
    
    return render_template('kelola_kategori.html', role=role_aktif, kategori_list=kategori_db, error=pesan_error)

@app.route('/admin/kategori/hapus/<int:kat_id>')
def hapus_kategori(kat_id):
    role_aktif = request.args.get('role', 'guest')
    if role_aktif == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM daftar_kategori WHERE id = ?", (kat_id,))
        conn.commit()
        conn.close()
    return redirect(url_for('kelola_kategori', role=role_aktif))
@app.route('/admin/klaim')
def admin_klaim():
    role_aktif = request.args.get('role', 'guest')
    if role_aktif != 'admin':
        flash("Akses ditolak! Anda bukan admin.", "gagal")
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Mengambil data klaim beserta info barang yang diklaim menggunakan JOIN
    cursor.execute('''
        SELECT klaim.*, barang.nama AS nama_barang, barang.tipe AS tipe_barang, barang.foto
        FROM klaim
        JOIN barang ON klaim.barang_id = barang.id
    ''')
    daftar_klaim = cursor.fetchall()
    conn.close()
    
    return render_template('admin_klaim.html', daftar_klaim=daftar_klaim, role=role_aktif)

@app.route('/admin/proses_klaim/<int:klaim_id>/<string:tindakan>')
def proses_klaim(klaim_id, tindakan):
    role_aktif = request.args.get('role', 'guest')
    if role_aktif != 'admin':
        return "Akses Ditolak", 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Ambil data barang_id sekaligus deskripsi pembuktian untuk cek tipe awal
   # Ubah query lama menjadi seperti ini (ditambahkan barang.kontak)
    cursor.execute(''' SELECT klaim.*, barang.nama AS nama_barang, barang.tipe AS tipe_barang, barang.foto, barang.kontak AS kontak_pelapor FROM klaim JOIN barang ON klaim.barang_id = barang.id ''')
    klaim_data = cursor.fetchone()
    
    if klaim_data:
        barang_id = klaim_data['barang_id']
        bukti_teks = klaim_data['bukti_detail']
        
        if tindakan == 'setujui':
            # Ubah status barang jadi 'Done' (Selesai)
            cursor.execute("UPDATE barang SET tipe = 'Done' WHERE id = ?", (barang_id,))
            cursor.execute("DELETE FROM klaim WHERE id = ?", (klaim_id,))
            flash("Klaim berhasil disetujui! Status barang kini 'Selesai'.", "sukses")
            
        elif tindakan == 'tolak':
            # 2. LOGIKA PINTAR: Ambil kontak dari database barang untuk tahu tipe aslinya
            cursor.execute("SELECT kontak FROM barang WHERE id = ?", (barang_id,))
            barang_data = cursor.fetchone()
            
            # Jika kolom kontak terisi, berarti itu barang 'Lost' (Pelapor mencantumkan kontak miliknya)
            # Jika kosong/tidak ada, berarti barang 'Found' milik posko admin
            if barang_data and barang_data['kontak']:
                status_asal = 'Lost'
            else:
                status_asal = 'Found'
                
            # Kembalikan status barang ke tipe aslinya secara akurat
            cursor.execute("UPDATE barang SET tipe = ? WHERE id = ?", (status_asal, barang_id))
            cursor.execute("DELETE FROM klaim WHERE id = ?", (klaim_id,))
            flash("Permintaan verifikasi ditolak. Barang dikembalikan ke daftar utama.", "info")
            
        conn.commit()
    conn.close()
    return redirect(url_for('admin_klaim', role=role_aktif))

if __name__ == '__main__':
    app.run(debug=True)