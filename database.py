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
