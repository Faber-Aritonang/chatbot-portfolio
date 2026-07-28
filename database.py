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
            created_at TEXT
        )
    """)
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
