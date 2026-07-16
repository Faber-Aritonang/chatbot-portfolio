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
