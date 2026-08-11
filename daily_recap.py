import datetime
import sqlite3
from telegram_helper import send_telegram_with_retry, GROUP_CHAT_ID

DB_FILE = "database.db"
TOPIC_ID_REKAP = 23  # Menampilkan rekap harian pada Topic Laporan (atau sesuaikan ID Topic lainnya)

def dapatkan_statistik_hari_ini():
    hari_ini = datetime.date.today().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Hitung Laporan Baru Masuk Hari Ini (Format string di DB: 'YYYY-MM-DD HH:MM')
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tanggal LIKE ?", (f"{hari_ini}%",))
    laporan_baru = cursor.fetchone()[0]
    
    # 2. Hitung Pengajuan Klaim Hari Ini
    cursor.execute("SELECT COUNT(*) FROM klaim WHERE tanggal_klaim LIKE ?", (f"{hari_ini}%",))
    klaim_masuk = cursor.fetchone()[0]
    
    # 3. Hitung Total Barang Selesai (Done)
    cursor.execute("SELECT COUNT(*) FROM barang WHERE tipe = 'Done'")
    total_selesai = cursor.fetchone()[0]
    
    conn.close()
    return laporan_baru, klaim_masuk, total_selesai

def send_daily_summary():
    tanggal_format = datetime.date.today().strftime("%d %B %Y")
    laporan, klaim, selesai = dapatkan_statistik_hari_ini()

    pesan = (
        f"📊 *RINGKASAN HARIAN LOST & FOUND*\n"
        f"📅 *Tanggal:* {tanggal_format}\n\n"
        f"• *Laporan Baru Hari Ini:* {laporan}\n"
        f"• *Pengajuan Klaim Hari Ini:* {klaim}\n"
        f"• *Total Barang Selesai (Done):* {selesai}\n\n"
        f"🔗 *Periksa antrean di website secara berkala!*"
    )

    payload = {
        "chat_id": GROUP_CHAT_ID,
        "message_thread_id": TOPIC_ID_REKAP,
        "text": pesan,
        "parse_mode": "Markdown"
    }

    send_telegram_with_retry(payload)

if __name__ == "__main__":
    send_daily_summary()