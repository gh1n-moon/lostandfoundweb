from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import sqlite3
import os
from functools import wraps
from werkzeug.utils import secure_filename
from telegram_helper import send_telegram_with_retry, GROUP_CHAT_ID

app = Flask(__name__)
app.secret_key = "kunci_rahasia_lostfound_unipol"

# Configuration Topic ID Telegram
TOPIC_ID_LAPORAN = 3
TOPIC_ID_KLAIM = 4

def kirim_notifikasi_telegram(kategori_atau_barang, tipe_laporan):
    """
    Mengirimkan notifikasi ke Telegram dengan automatic retry dan logging handler.
    """
    if "Klaim" in tipe_laporan or "Pengajuan" in tipe_laporan:
        target_topic = TOPIC_ID_KLAIM
        pesan = (
            "📩 *PENGAJUAN KLAIM BARU*\n\n"
            f"• *Detail:* {kategori_atau_barang}\n"
            f"• *Kategori:* {tipe_laporan}\n\n"
            "🔗 *Silakan periksa Antrean Klaim di website.*"
        )
    else:
        target_topic = TOPIC_ID_LAPORAN
        pesan = (
            "📦 *LAPORAN BARU MASUK*\n\n"
            f"• *Nama Barang:* {kategori_atau_barang}\n"
            f"• *Tipe/Kategori:* {tipe_laporan}\n\n"
            "🔗 *Silakan periksa Antrean Persetujuan di website.*"
        )

    payload = {
        "chat_id": GROUP_CHAT_ID,
        "message_thread_id": target_topic,
        "text": pesan,
        "parse_mode": "Markdown"
    }

    send_telegram_with_retry(payload)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin"):
            flash("Silakan login sebagai Admin terlebih dahulu!", "gagal")
            return redirect(url_for("welcome"))
        return f(*args, **kwargs)
    return decorated_function

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = "database.db"

# ==============================================================================
# FITUR 1: PROFANITY FILTER
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
# UTILITAS DATABASE
# ==============================================================================
def get_db_connection():
    conn = sqlite3.connect(DB_FILE) 
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE barang ADD COLUMN foto TEXT DEFAULT 'default.jpg';")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE barang ADD COLUMN nama_pelapor TEXT DEFAULT '-';")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE klaim ADD COLUMN jenis_klaim TEXT DEFAULT 'Pengklaim';")
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS klaim (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barang_id INTEGER,
            nama_klaim TEXT NOT NULL,
            nim_klaim TEXT NOT NULL,
            wa_klaim TEXT NOT NULL,
            bukti_detail TEXT NOT NULL,
            tanggal_klaim TEXT NOT NULL,
            jenis_klaim TEXT DEFAULT 'Pengklaim',
            FOREIGN KEY (barang_id) REFERENCES barang (id)
        )
    ''')
    conn.commit()
    return conn

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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daftar_kategori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_kategori TEXT NOT NULL UNIQUE
        )
    ''')
    
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
            session['admin'] = True
            return redirect(url_for('index'))
        else:
            session.pop('admin', None)
            pesan_error = "Kata sandi Admin salah!"
    return render_template('welcome.html', error=pesan_error)

@app.route('/index')
def index():
    status_tab = request.args.get('status', 'all')
    kategori_filter = request.args.get('kategori', '')
    pencarian = request.args.get('search', '').lower()
    role_aktif = "admin" if session.get("admin") else "guest"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Lost'")
    total_hilang = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Found'")
    total_ditemukan = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Dalam_Proses_Klaim'")
    total_verifikasi = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Done'")
    total_selesai = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe LIKE 'Pending_%'")
    total_pending = cursor.fetchone()[0]
    
    query = "SELECT * FROM barang WHERE 1=1"
    params = []
    
    if status_tab == 'Lost':
        query += " AND tipe = 'Lost'"
    elif status_tab == 'Found':
        query += " AND tipe = 'Found'"
    elif status_tab == 'Done':
        query += " AND tipe = 'Done'"
    elif status_tab == 'Dalam_Proses_Klaim':
        query += " AND tipe = 'Dalam_Proses_Klaim'"
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
                           verifikasi_count=total_verifikasi,
                           selesai=total_selesai,
                           pending_count=total_pending,
                           kategori_list=kategori_db, 
                           role=role_aktif)

@app.route('/setujui/<int:barang_id>')
@admin_required
def setujui(barang_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tipe FROM barang WHERE id=?", (barang_id,))
    row = cursor.fetchone()

    if row:
        tipe_asli = row["tipe"].replace("Pending_", "")
        cursor.execute("UPDATE barang SET tipe=? WHERE id=?", (tipe_asli, barang_id))
        conn.commit()

    conn.close()
    return redirect(url_for("index", status="Pending"))

@app.route('/hapus/<int:barang_id>')
@admin_required
def hapus(barang_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM barang WHERE id=?", (barang_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route('/laporkan', methods=['GET', 'POST'])
def laporkan():
    role_aktif = request.args.get('role', 'guest')
    pesan_error = None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        tipe = request.form.get('tipe')
        nama_pelapor = request.form.get('nama_pelapor')
        nama = request.form.get('nama')
        kategori = request.form.get('kategori')
        lokasi = request.form.get('lokasi')
        deskripsi = request.form.get('deskripsi')
        kontak = request.form.get('kontak')
        tanggal_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")

        cursor.execute("SELECT * FROM daftar_kategori ORDER BY id ASC")
        kategori_db = cursor.fetchall()

        if mengandung_kata_kasar(nama_pelapor) or mengandung_kata_kasar(nama) or mengandung_kata_kasar(lokasi) or mengandung_kata_kasar(deskripsi):
            pesan_error = "Laporan ditolak! Harap tidak menggunakan kata-kata kasar/sensitif."
            conn.close()
            return render_template('laporkan.html', error=pesan_error, role=role_aktif, kategori_list=kategori_db)

        file_foto = request.files.get('foto_barang')
        if file_foto and file_foto.filename != '':
            filename = secure_filename(file_foto.filename)
            jalur_simpan = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file_foto.save(jalur_simpan)
        else:
            filename = 'default.jpg'

        status_pending = f"Pending_{tipe}"

        cursor.execute('''
            INSERT INTO barang (tipe, nama_pelapor, nama, kategori, lokasi, deskripsi, kontak, tanggal, foto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (status_pending, nama_pelapor, nama, kategori, lokasi, deskripsi, kontak, tanggal_sekarang, filename))
        
        conn.commit()
        conn.close()
        
        kirim_notifikasi_telegram(nama, tipe)

        flash("Laporan Anda berhasil dikirim! Laporan sedang berada dalam antrean peninjauan Admin sebelum diterbitkan ke publik.", "sukses_pending")
        return redirect(url_for('index', role=role_aktif))

    cursor.execute("SELECT * FROM daftar_kategori ORDER BY id ASC")
    kategori_db = cursor.fetchall()
    conn.close()
    
    return render_template('laporkan.html', role=role_aktif, error=pesan_error, kategori_list=kategori_db)

@app.route('/klaim/<int:barang_id>', methods=['GET', 'POST'])
def klaim(barang_id):
    if session.get('admin'):
        role_aktif = 'admin'
    else:
        role_aktif = request.args.get('role', 'guest')
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM barang WHERE id = ?", (barang_id,))
    barang_data = cursor.fetchone()
    
    if not barang_data:
        conn.close()
        flash("Data barang tidak ditemukan!", "gagal")
        return redirect(url_for('index', role=role_aktif))
        
    if request.method == 'GET':
        conn.close()
        return render_template('klaim.html', item=barang_data, role=role_aktif)

    nama_klaim = request.form.get('nama_klaim')
    wa_klaim = request.form.get('wa_klaim')
    bukti_detail = request.form.get('bukti_detail')
    nim_klaim = "-"
    tanggal_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    jenis_peran = request.form.get('jenis_klaim', 'Pengklaim')
    
    if not nama_klaim or not wa_klaim or not bukti_detail:
        conn.close()
        flash("Semua kolom formulir wajib diisi!", "gagal")
        return redirect(url_for('index', role=role_aktif))
    
    if mengandung_kata_kasar(nama_klaim) or mengandung_kata_kasar(bukti_detail):
        conn.close()
        flash("Permintaan ditolak! Harap tidak menggunakan kata-kata kasar.", "gagal")
        return redirect(url_for('index', role=role_aktif))
    
    cursor.execute('''
        INSERT INTO klaim (barang_id, nama_klaim, nim_klaim, wa_klaim, bukti_detail, tanggal_klaim, jenis_klaim)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (barang_id, nama_klaim, nim_klaim, wa_klaim, bukti_detail, tanggal_sekarang, jenis_peran))
    
    cursor.execute("UPDATE barang SET tipe = 'Dalam_Proses_Klaim' WHERE id = ?", (barang_id,))
    
    conn.commit()
    conn.close()
    
    kirim_notifikasi_telegram(f"Barang ID #{barang_id}", "Pengajuan Klaim")

    flash("Informasi berhasil dikirim! Admin akan segera meninjau laporan Anda.", "sukses_pending")
    return redirect(url_for('index', role=role_aktif))

@app.route('/admin/kategori', methods=['GET','POST'])
@admin_required
def kelola_kategori():
    role_aktif = "admin"
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
@admin_required
def hapus_kategori(kat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daftar_kategori WHERE id=?", (kat_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("kelola_kategori"))

@app.route('/admin/klaim')
@admin_required
def admin_klaim():
    role_aktif = request.args.get('role', 'guest')
    if role_aktif != 'admin':
        flash("Akses ditolak! Anda bukan admin.", "gagal")
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            klaim.*, 
            barang.nama AS nama_barang, 
            barang.tipe AS tipe_barang, 
            barang.nama_pelapor,
            barang.foto,
            barang.kontak AS kontak_pelapor
        FROM klaim
        JOIN barang ON klaim.barang_id = barang.id
    ''')
    daftar_klaim = cursor.fetchall()
    conn.close()
    
    return render_template('admin_klaim.html', daftar_klaim=daftar_klaim, role=role_aktif)

@app.route('/admin/proses_klaim/<int:klaim_id>/<string:tindakan>')
@admin_required
def proses_klaim(klaim_id, tindakan):
    role_aktif = request.args.get('role', 'guest')
    if role_aktif != 'admin' and not session.get('admin'):
        return "Akses Ditolak", 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM klaim WHERE id = ?", (klaim_id,))
    klaim_data = cursor.fetchone()
    
    if klaim_data:
        barang_id = klaim_data['barang_id']
        if tindakan == 'setujui':
            cursor.execute("UPDATE barang SET tipe = 'Done' WHERE id = ?", (barang_id,))
            cursor.execute("DELETE FROM klaim WHERE id = ?", (klaim_id,))
            flash("Klaim berhasil disetujui! Status barang kini 'Selesai'.", "sukses")
        elif tindakan == 'tolak':
            jenis_k = klaim_data['jenis_klaim'] if 'jenis_klaim' in klaim_data.keys() else 'Pengklaim'
            status_asal = 'Lost' if jenis_k == 'Penemu' else 'Found'
            cursor.execute("UPDATE barang SET tipe = ? WHERE id = ?", (status_asal, barang_id))
            cursor.execute("DELETE FROM klaim WHERE id = ?", (klaim_id,))
            flash("Permintaan verifikasi ditolak. Barang dikembalikan ke daftar utama.", "info")
            
        conn.commit()
    conn.close()
    return redirect(url_for('admin_klaim', role=role_aktif))

@app.route('/hapus_masal', methods=['POST'])
def hapus_masal():
    role_aktif = request.form.get('role', 'guest')
    status_tab = request.form.get('status', 'all')
    
    if not session.get('admin') and role_aktif != 'admin':
        flash("Akses ditolak! Hanya admin yang dapat melakukan aksi ini.", "gagal")
        return redirect(url_for('index', role=role_aktif, status=status_tab))
        
    ids_terpilih = request.form.getlist('item_ids')
    if ids_terpilih:
        conn = get_db_connection()
        cursor = conn.cursor()
        for b_id in ids_terpilih:
            cursor.execute("SELECT foto FROM barang WHERE id = ?", (b_id,))
            item = cursor.fetchone()
            if item and item['foto'] and item['foto'] != 'default.jpg':
                path_foto = os.path.join(app.config['UPLOAD_FOLDER'], item['foto'])
                if os.path.exists(path_foto):
                    try:
                        os.remove(path_foto)
                    except Exception:
                        pass
            cursor.execute("DELETE FROM klaim WHERE barang_id = ?", (b_id,))
            cursor.execute("DELETE FROM barang WHERE id = ?", (b_id,))
            
        conn.commit()
        conn.close()
        flash(f"Berhasil menghapus {len(ids_terpilih)} barang sekaligus!", "sukses_pending")
    else:
        flash("Tidak ada barang yang dipilih untuk dihapus.", "info")
        
    return redirect(url_for('index', role=role_aktif, status=status_tab))

@app.route('/aksi_masal_pending', methods=['POST'])
def aksi_masal_pending():
    role_aktif = request.form.get('role', 'guest')
    status_tab = request.form.get('status', 'Pending')
    
    if not session.get('admin') and role_aktif != 'admin':
        flash("Akses ditolak! Hanya admin yang dapat melakukan aksi ini.", "gagal")
        return redirect(url_for('index', role=role_aktif, status=status_tab))
        
    ids_terpilih = request.form.getlist('item_ids')
    tindakan = request.form.get('tindakan')
    
    if ids_terpilih:
        conn = get_db_connection()
        cursor = conn.cursor()
        if tindakan == 'setujui':
            for b_id in ids_terpilih:
                cursor.execute("SELECT tipe FROM barang WHERE id = ?", (b_id,))
                item = cursor.fetchone()
                if item and 'Pending_' in item['tipe']:
                    status_baru = item['tipe'].replace('Pending_', '')
                    cursor.execute("UPDATE barang SET tipe = ? WHERE id = ?", (status_baru, b_id))
            conn.commit()
            conn.close()
            flash(f"Berhasil menyetujui {len(ids_terpilih)} laporan!", "sukses_pending")
        elif tindakan == 'tolak':
            for b_id in ids_terpilih:
                cursor.execute("SELECT foto FROM barang WHERE id = ?", (b_id,))
                item = cursor.fetchone()
                if item and item['foto'] and item['foto'] != 'default.jpg':
                    path_foto = os.path.join(app.config['UPLOAD_FOLDER'], item['foto'])
                    if os.path.exists(path_foto):
                        try:
                            os.remove(path_foto)
                        except Exception:
                            pass
                cursor.execute("DELETE FROM barang WHERE id = ?", (b_id,))
            conn.commit()
            conn.close()
            flash(f"Berhasil menolak {len(ids_terpilih)} laporan pending.", "info")
    else:
        flash("Tidak ada laporan yang dipilih.", "info")
        
    return redirect(url_for('index', role=role_aktif, status=status_tab))

@app.route('/logout')
def logout():
    session.clear()
    flash("Berhasil logout.", "info")
    return redirect(url_for('welcome'))

if __name__ == '__main__':
    app.run(debug=True)