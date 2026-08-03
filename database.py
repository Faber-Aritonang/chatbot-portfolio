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


def init_rating_table():
    """Membuat tabel rating dan tambah kolom feedback_sent ke bookings"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER,
            user_id TEXT,
            layanan TEXT,
            rating INTEGER,
            created_at TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE bookings ADD COLUMN feedback_sent INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def get_bookings_untuk_feedback(tanggal):
    """Ambil booking yang jadwalnya kemarin dan belum diminta feedback"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, layanan, tanggal FROM bookings
        WHERE tanggal = ? AND status = 'confirmed' AND feedback_sent = 0
    """, (tanggal,))
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def tandai_feedback_terkirim(booking_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET feedback_sent = 1 WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def save_rating(booking_id, user_id, layanan, rating):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ratings (booking_id, user_id, layanan, rating, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (booking_id, user_id, layanan, rating, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_all_customer_ids():
    """Ambil semua user_id pelanggan yang pernah berinteraksi dengan bot"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM customers")
    hasil = cursor.fetchall()
    conn.close()
    return [row[0] for row in hasil]


def get_semua_bookings():
    """Ambil semua data booking untuk keperluan export"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, username, layanan, tanggal, status, created_at
        FROM bookings
        ORDER BY created_at DESC
    """)
    hasil = cursor.fetchall()
    conn.close()
    return hasil


def init_processed_messages_table():
    """Tabel untuk melacak message_id WhatsApp yang sudah diproses (cegah duplikat)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_messages (
            message_id TEXT PRIMARY KEY,
            processed_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def sudah_diproses(message_id):
    """Cek apakah message_id ini sudah pernah diproses sebelumnya"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT message_id FROM processed_messages WHERE message_id = ?", (message_id,))
    hasil = cursor.fetchone()
    conn.close()
    return hasil is not None

def tandai_sudah_diproses(message_id):
    """Catat message_id sebagai sudah diproses"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
        (message_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def init_allowed_users_table():
    """Tabel whitelist user yang diizinkan memakai bot"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS allowed_users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            added_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_user_allowed(user_id):
    """Cek apakah user_id ada di whitelist"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM allowed_users WHERE user_id = ?", (user_id,))
    hasil = cursor.fetchone()
    conn.close()
    return hasil is not None

def add_allowed_user(user_id, username):
    """Tambahkan user ke whitelist"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO allowed_users (user_id, username, added_at) VALUES (?, ?, ?)",
        (user_id, username, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def remove_allowed_user(user_id):
    """Hapus user dari whitelist"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM allowed_users WHERE user_id = ?", (user_id,))
    berhasil = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return berhasil


def get_booking_per_layanan():
    """Hitung jumlah booking confirmed per layanan, untuk grafik populeritas"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT layanan, COUNT(*) as jumlah
        FROM bookings
        WHERE status = 'confirmed'
        GROUP BY layanan
        ORDER BY jumlah DESC
    """)
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def get_booking_trend(hari=30):
    """Tren jumlah booking dibuat per tanggal, N hari terakhir"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(created_at) as tgl, COUNT(*) as jumlah
        FROM bookings
        WHERE created_at >= DATE('now', ?)
        GROUP BY tgl
        ORDER BY tgl ASC
    """, (f'-{hari} days',))
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def get_rating_rata_rata_per_layanan():
    """Rata-rata rating per layanan"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT layanan, ROUND(AVG(rating), 2) as rata_rata, COUNT(*) as jumlah_rating
        FROM ratings
        GROUP BY layanan
        ORDER BY rata_rata DESC
    """)
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def get_complaint_counts_by_status():
    """Jumlah komplain per status (baru vs ditanggapi)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status, COUNT(*) as jumlah
        FROM complaints
        GROUP BY status
    """)
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def get_ringkasan_stats():
    """Angka ringkasan untuk kartu statistik di dashboard"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE status='confirmed'")
    total_booking = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM customers")
    total_pelanggan = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status='baru'")
    komplain_belum_ditanggapi = cursor.fetchone()[0]
    cursor.execute("SELECT ROUND(AVG(rating), 2) FROM ratings")
    rating_rata_rata = cursor.fetchone()[0] or 0
    conn.close()
    return {
        "total_booking": total_booking,
        "total_pelanggan": total_pelanggan,
        "komplain_belum_ditanggapi": komplain_belum_ditanggapi,
        "rating_rata_rata": rating_rata_rata,
    }
