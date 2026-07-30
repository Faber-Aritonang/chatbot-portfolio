import sqlite3
from datetime import datetime

DB_NAME = "chatbot.db"

def init_db():
    """Membuat tabel kalau belum ada"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            message TEXT,
            reply TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_conversation(user_id, username, message, reply):
    """Simpan 1 percakapan ke database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO conversations (user_id, username, message, reply, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, message, reply, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_recent_conversations(limit=10):
    """Ambil beberapa percakapan terakhir (untuk cek/debug)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT username, message, reply, timestamp 
        FROM conversations 
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_bookings_untuk_reminder(tanggal):
    """Ambil booking yang jadwalnya besok dan belum dikirimi reminder"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, layanan, tanggal FROM bookings
        WHERE tanggal = ? AND status = 'confirmed' AND reminded = 0
    """, (tanggal,))
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def tandai_sudah_diingatkan(booking_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def save_booking(user_id, username, layanan, tanggal):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bookings (user_id, username, layanan, tanggal, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username, layanan, tanggal, "confirmed", datetime.now().isoformat()))
    conn.commit()
    conn.close()

def hitung_booking_pada_tanggal(layanan, tanggal):
    """Hitung berapa booking yang sudah ada untuk layanan & tanggal tertentu"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM bookings
        WHERE layanan = ? AND tanggal = ? AND status = 'confirmed'
    """, (layanan, tanggal))
    hasil = cursor.fetchone()
    conn.close()
    return hasil[0] if hasil else 0

def get_user_bookings(user_id):
    """Ambil semua booking aktif (confirmed) milik seorang user"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, layanan, tanggal FROM bookings
        WHERE user_id = ? AND status = 'confirmed'
        ORDER BY tanggal ASC
    """, (user_id,))
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def cancel_booking(booking_id, user_id):
    """Batalkan booking, hanya jika booking itu milik user yang meminta"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE bookings SET status = 'cancelled'
        WHERE id = ? AND user_id = ?
    """, (booking_id, user_id))
    berhasil = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return berhasil



def init_booking_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            layanan TEXT,
            tanggal TEXT,
            status TEXT,
            created_at TEXT,
            reminded INTEGER DEFAULT 0
        )
    """)
    try:
        cursor.execute("ALTER TABLE bookings ADD COLUMN reminded INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def init_customer_table():
    """Membuat tabel profil pelanggan"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            nama_panggilan TEXT,
            total_booking INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT
        )
    """)
    conn.commit()
    conn.close()

def upsert_customer(user_id, username):
    """Simpan atau update data pelanggan setiap kali mereka berinteraksi"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("SELECT user_id FROM customers WHERE user_id = ?", (user_id,))
    ada = cursor.fetchone()
    if ada:
        cursor.execute("""
            UPDATE customers SET username = ?, last_seen = ? WHERE user_id = ?
        """, (username, now, user_id))
    else:
        cursor.execute("""
            INSERT INTO customers (user_id, username, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, now, now))
    conn.commit()
    conn.close()

def get_customer(user_id):
    """Ambil data profil pelanggan, None kalau belum pernah interaksi"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nama_panggilan, total_booking FROM customers WHERE user_id = ?", (user_id,))
    hasil = cursor.fetchone()
    conn.close()
    return hasil

def tambah_hitungan_booking(user_id):
    """Naikkan counter total booking pelanggan"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE customers SET total_booking = total_booking + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def init_complaint_table():
    """Membuat tabel untuk mencatat komplain pelanggan"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            isi_komplain TEXT,
            status TEXT DEFAULT 'baru',
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_complaint(user_id, username, isi_komplain):
    """Simpan komplain baru dengan status 'baru' (menunggu ditindaklanjuti), kembalikan ID-nya"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO complaints (user_id, username, isi_komplain, status, created_at)
        VALUES (?, ?, ?, 'baru', ?)
    """, (user_id, username, isi_komplain, datetime.now().isoformat()))
    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return complaint_id


def get_complaint(complaint_id):
    """Ambil detail 1 komplain berdasarkan ID"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, username, isi_komplain, status FROM complaints WHERE id = ?", (complaint_id,))
    hasil = cursor.fetchone()
    conn.close()
    return hasil

def update_complaint_status(complaint_id, status):
    """Update status komplain, misal jadi 'ditanggapi'"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET status = ? WHERE id = ?", (status, complaint_id))
    conn.commit()
    conn.close()


def get_riwayat_percakapan_user(user_id, limit=5):
    """Ambil beberapa percakapan terakhir milik user tertentu, urut dari lama ke baru"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message, reply FROM conversations
        WHERE user_id = ?
        ORDER BY id DESC LIMIT ?
    """, (user_id, limit))
    hasil = cursor.fetchall()
    conn.close()
    return list(reversed(hasil))  # balik urutan supaya dari lama ke baru
