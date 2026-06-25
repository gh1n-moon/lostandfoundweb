from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import pandas as pd
import os

app = Flask(__name__)

FILE_EXCEL = "database_lostfound.xlsx"

# Fungsi untuk membaca data dari Excel ke dalam bentuk List of Dictionaries
def baca_dari_excel():
    if not os.path.exists(FILE_EXCEL):
        df_baru = pd.DataFrame(columns=["id", "tipe", "nama", "kategori", "lokasi", "deskripsi", "kontak", "tanggal"])
        df_baru.to_excel(FILE_EXCEL, index=False)
        return []
    
    df = pd.read_excel(FILE_EXCEL, dtype={"id": "Int64", "kontak": str})
    df[["tipe", "nama", "kategori", "lokasi", "deskripsi", "tanggal"]] = df[["tipe", "nama", "kategori", "lokasi", "deskripsi", "tanggal"]].fillna("")
    df["kontak"] = df["kontak"].fillna("")
    
    # Konversi ke dict dan pastikan ID murni berupa integer biasa (int) saat masuk ke list
    daftar_data = df.to_dict(orient="records")
    for b in daftar_data:
        if pd.notna(b['id']):
            b['id'] = int(b['id'])
            
    return daftar_data

# Fungsi untuk menyimpan kembali data List to file Excel
def simpan_ke_excel(daftar_data):
    df = pd.DataFrame(daftar_data)
    df.to_excel(FILE_EXCEL, index=False)

def database_kategori_check(daftar, kat):
    return [b for b in daftar if b['kategori'] == kat]

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
    
    # Ambil data terbaru dari file Excel
    data_barang = baca_dari_excel()
    
    # Menghitung Statistik Secara Real-time untuk Dashboard Atas
    total_hilang = len([b for b in data_barang if b['tipe'] == 'Lost'])
    total_ditemukan = len([b for b in data_barang if b['tipe'] == 'Found'])
    total_selesai = len([b for b in data_barang if b['tipe'] == 'Done'])
    
    # Filter Berdasarkan Tab Aktif
    if status_tab == 'Lost':
        hasil_filter = [b for b in data_barang if b['tipe'] == 'Lost']
    elif status_tab == 'Found':
        hasil_filter = [b for b in data_barang if b['tipe'] == 'Found']
    elif status_tab == 'Done':
        hasil_filter = [b for b in data_barang if b['tipe'] == 'Done']
    else:
        hasil_filter = [b for b in data_barang if b['tipe'] != 'Done']
    
    # Filter Pencarian Teks dan Dropdown Kategori
    if kategori_filter:
        hasil_filter = database_kategori_check(hasil_filter, kategori_filter)
    if pencarian:
        hasil_filter = [b for b in hasil_filter if pencarian in str(b['nama']).lower() or pencarian in str(b['deskripsi']).lower()]
        
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
# 3. PROSES MENGUBAH STATUS BARANG (TETAP REDIRECT KE INDEX FUNGSI UTAMA)
# ==============================================================================
@app.route('/selesai/<int:barang_id>')
def selesai(barang_id):
    role_aktif = request.args.get('role', 'guest')
    
    if role_aktif == 'admin':
        data_barang = baca_dari_excel()
        for barang in data_barang:
            if barang['id'] == barang_id:
                barang['tipe'] = 'Done'
                break
        simpan_ke_excel(data_barang) # Update file Excel
                
    return redirect(url_for('index', status=request.args.get('status', 'all'), role=role_aktif))


# ==============================================================================
# 4. PROSES HAPUS BARANG (TETAP REDIRECT KE INDEX FUNGSI UTAMA)
# ==============================================================================
@app.route('/hapus/<int:barang_id>')
def hapus(barang_id):
    role_aktif = request.args.get('role', 'guest')
    
    if role_aktif == 'admin':
        data_barang = baca_dari_excel()
        data_barang = [b for b in data_barang if b['id'] != barang_id]
        simpan_ke_excel(data_barang) # Update file Excel
        
    return redirect(url_for('index', status=request.args.get('status', 'all'), role=role_aktif))

# ==============================================================================
# 5. HALAMAN LAPOR BARANG BARU (TETAP REDIRECT KE INDEX FUNGSI UTAMA)
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

        # Ambil data lama, buat nomor ID baru secara auto-increment
        data_barang = baca_dari_excel()
        baru_id = max([b['id'] for b in data_barang], default=0) + 1

        # Ikat ke dalam struktur dictionary data
        item_baru = {
            "id": baru_id,
            "tipe": tipe,
            "nama": nama,
            "kategori": kategori,
            "lokasi": lokasi,
            "deskripsi": deskripsi,
            "kontak": kontak,
            "tanggal": tanggal_sekarang
        }

        # Simpan ke Excel
        data_barang.append(item_baru)
        simpan_ke_excel(data_barang)

        # Lempar kembali ke halaman utama dashboard dengan role yang sama
        return redirect(url_for('index', role=role_aktif))

    return render_template('laporkan.html', role=role_aktif)


# ==============================================================================
# RUNNER SERVER UTAMA (WAJIB DI PALING BAWAH DAN MENUTUP FILE)
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True)