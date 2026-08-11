import logging
import time
import requests

# Konfigurasi Logging ke file app.log
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

BOT_TOKEN = "8692387315:AAEpkVvAH4u4g-4jmn9uazfr9tNfs3A9yGE"
GROUP_CHAT_ID = "-1004466603212"

def send_telegram_with_retry(payload, max_retries=3, delay=2):
    """
    Mencoba mengirim notifikasi ke Telegram dengan batas re-try otomatis jika gagal.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logging.info(f"Notifikasi terkirim ke topic ID: {payload.get('message_thread_id')}")
                return True
            else:
                logging.warning(f"Attempt {attempt}/{max_retries} Gagal. HTTP Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Attempt {attempt}/{max_retries} Exception: {e}")

        if attempt < max_retries:
            time.sleep(delay)

    logging.critical(f"GAGAL TOTAL: Tidak dapat mengirim notifikasi Telegram: {payload}")
    return False