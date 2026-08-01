import asyncio
import csv
import io
from collections import defaultdict
from telegram.error import TimedOut, NetworkError
from datetime import datetime
from database import init_db, save_conversation, init_booking_table, save_booking, hitung_booking_pada_tanggal, get_user_bookings, cancel_booking, get_bookings_untuk_reminder, tandai_sudah_diingatkan, init_customer_table, upsert_customer, get_customer, tambah_hitungan_booking, init_complaint_table, save_complaint, get_complaint, update_complaint_status, get_riwayat_percakapan_user, init_rating_table, get_bookings_untuk_feedback, tandai_feedback_terkirim, save_rating, get_all_customer_ids, get_semua_bookings, init_allowed_users_table, is_user_allowed, add_allowed_user, remove_allowed_user, init_allowed_users_table, is_user_allowed, add_allowed_user, remove_allowed_user, init_allowed_users_table, is_user_allowed, add_allowed_user, remove_allowed_user
import os
from datetime import datetime, timedelta, time
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from openai import OpenAI

# Muat variabel dari .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup koneksi ke Qwen lewat Ollama
llm_client = OpenAI(
    base_url="https://api.anthropic.com/v1/",
    api_key=os.getenv("ANTHROPIC_API_KEY")
)
async def kirim_pesan_aman(update_or_query, text, reply_markup=None, max_retry=3):
    """
    Kirim pesan dengan retry otomatis kalau terjadi gangguan jaringan.
    Bisa dipakai untuk update.message.reply_text ATAU query.edit_message_text.
    """
    for percobaan in range(1, max_retry + 1):
        try:
            if hasattr(update_or_query, "message"):
                # ini adalah 'update', pakai reply_text
                await update_or_query.message.reply_text(text, reply_markup=reply_markup)
            else:
                # ini adalah 'query' (callback), pakai edit_message_text
                await update_or_query.edit_message_text(text, reply_markup=reply_markup)
            return True  # berhasil, keluar dari loop
        except (TimedOut, NetworkError) as e:
            print(f"Percobaan {percobaan}/{max_retry} gagal: {e}")
            if percobaan < max_retry:
                await asyncio.sleep(2)  # tunggu 2 detik sebelum coba lagi
            else:
                print(f"Gagal kirim pesan setelah {max_retry} percobaan.")
                return False

# State untuk alur booking
PILIH_LAYANAN, INPUT_TANGGAL, KONFIRMASI = range(3)
KAPASITAS_PER_HARI = 3  # maksimal booking per layanan per tanggal

# Handler untuk command /start - sekarang dengan tombol interaktif
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "unknown"

    # Catat/perbarui profil pelanggan setiap kali mereka mulai chat
    upsert_customer(user_id, username)
    customer = get_customer(user_id)

    keyboard = [
        [InlineKeyboardButton("💬 Chat Bebas", callback_data="chat_bebas")],
        [InlineKeyboardButton("📅 Booking", callback_data="menu_booking")],
        [InlineKeyboardButton("ℹ️ Tentang Bot", callback_data="tentang")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Sapaan berbeda untuk pelanggan lama vs baru
    if customer and customer[3] > 0:  # total_booking > 0
        pesan_sapaan = f"Halo lagi! Senang bertemu Anda kembali 😊 (booking Anda sejauh ini: {customer[3]}x)"
    else:
        pesan_sapaan = "Halo! Saya bot Si Dodol. Pilih menu di bawah atau langsung ketik pesan bebas:"

    await update.message.reply_text(pesan_sapaan, reply_markup=reply_markup)

# Handler saat tombol di-klik
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # wajib ada, supaya tombol tidak "loading" terus

    if query.data == "chat_bebas":
        await query.edit_message_text("Silakan ketik pertanyaan Anda, saya akan coba jawab 🙂")
    elif query.data == "menu_booking":
        await query.edit_message_text("Untuk membuat booking, silakan ketik /booking")
    elif query.data == "tentang":
        await query.edit_message_text(
            "Saya adalah bot demo, SiDodol, yang dibuat Jimmy Faber untuk belajar chatbot development.\n"
            "Ditenagai oleh Qwen 2.5 7B (LLM lokal)."
        )

# Handler untuk command /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Perintah yang tersedia:\n/start - Mulai chat\n/help - Bantuan\nAtau ketik pesan bebas untuk chat dengan AI."
    )

# Handler untuk pesan teks bebas - sekarang dengan fallback handling

# Data FAQ tetap - jawaban langsung tanpa perlu panggil LLM
FAQ_JAWABAN = {
    "jam": "Jam operasional kami: Senin-Sabtu, 09.00 - 20.00 WIB.",
    "lokasi": "Lokasi kami: Jl. Contoh No. 123, Tangerang, Banten.",
    "harga": "Harga layanan mulai dari Rp50.000 tergantung jenis layanan. Ketik /booking untuk melihat pilihan layanan.",
}

def deteksi_intent(teks: str) -> str:
    """Deteksi maksud user berdasarkan kata kunci sederhana"""
    teks_lower = teks.lower()

    kata_kunci_booking = ["booking", "pesan", "reservasi", "jadwal"]
    kata_kunci_komplain = ["komplain", "keluhan", "kecewa", "buruk", "jelek", "tidak puas", "protes"]
    kata_kunci_jam = ["jam buka", "jam operasional", "jam berapa", "buka jam"]
    kata_kunci_lokasi = ["lokasi", "alamat", "dimana", "di mana"]
    kata_kunci_harga = ["harga", "biaya", "tarif", "berapa harga"]

    if any(kata in teks_lower for kata in kata_kunci_komplain):
        return "komplain"
    if any(kata in teks_lower for kata in kata_kunci_jam):
        return "faq_jam"
    if any(kata in teks_lower for kata in kata_kunci_lokasi):
        return "faq_lokasi"
    if any(kata in teks_lower for kata in kata_kunci_harga):
        return "faq_harga"
    if any(kata in teks_lower for kata in kata_kunci_booking):
        return "booking"

    return "umum"


# Rate limiting: lacak waktu pesan per user (in-memory, reset kalau bot di-restart)
riwayat_waktu_pesan = defaultdict(list)
MAX_PESAN_PER_MENIT = 5

def cek_rate_limit(user_id: str) -> bool:
    """Return True kalau user masih boleh kirim pesan, False kalau kena limit"""
    sekarang = datetime.now()
    satu_menit_lalu = sekarang - timedelta(minutes=1)

    # Buang catatan waktu yang sudah lebih dari 1 menit
    riwayat_waktu_pesan[user_id] = [
        waktu for waktu in riwayat_waktu_pesan[user_id] if waktu > satu_menit_lalu
    ]

    if len(riwayat_waktu_pesan[user_id]) >= MAX_PESAN_PER_MENIT:
        return False

    riwayat_waktu_pesan[user_id].append(sekarang)
    return True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "unknown"

    # Whitelist: hanya user yang diizinkan admin yang boleh pakai bot
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if user_id != admin_id and not is_user_allowed(user_id):
        await update.message.reply_text(
            "Maaf, bot ini masih dalam tahap demo terbatas. Silakan hubungi admin untuk mendapatkan akses. 🙏"
        )
        return

    # Whitelist: hanya user yang diizinkan admin yang boleh pakai bot
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if user_id != admin_id and not is_user_allowed(user_id):
        await update.message.reply_text(
            "Maaf, bot ini masih dalam tahap demo terbatas. Silakan hubungi admin untuk mendapatkan akses. 🙏"
        )
        return

    # Whitelist: hanya user yang diizinkan admin yang boleh pakai bot
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if user_id != admin_id and not is_user_allowed(user_id):
        await update.message.reply_text(
            "Maaf, bot ini masih dalam tahap demo terbatas. Silakan hubungi admin untuk mendapatkan akses. 🙏"
        )
        return

    # Rate limiting: cegah 1 user spam terlalu banyak pesan
    if not cek_rate_limit(user_id):
        await update.message.reply_text(
            "Anda mengirim pesan terlalu cepat. Mohon tunggu sebentar sebelum kirim pesan lagi 🙏"
        )
        return

    # Fallback sederhana: kalau pesan terlalu pendek/tidak jelas
    if len(user_text.strip()) < 2:
        await update.message.reply_text("Pesan Anda terlalu pendek, coba tulis lebih lengkap ya 🙂")
        return

    intent = deteksi_intent(user_text)

    if intent == "booking":
        await update.message.reply_text("Sepertinya Anda ingin membuat booking. Silakan ketik /booking untuk memulai.")
        return

    if intent == "komplain":
        complaint_id = save_complaint(user_id, username, user_text)
        await update.message.reply_text(
            "Mohon maaf atas ketidaknyamanannya 🙏 Keluhan Anda sudah kami catat dan akan segera ditindaklanjuti oleh tim kami."
        )

        # Eskalasi ke admin
        admin_id = os.getenv("ADMIN_TELEGRAM_ID")
        if admin_id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"⚠️ KOMPLAIN BARU (ID: {complaint_id})\n"
                        f"Dari: @{username} (user_id: {user_id})\n"
                        f"Isi: {user_text}\n\n"
                        f"Balas dengan /tanggapi {complaint_id} <pesan> untuk merespons."
                    )
                )
            except Exception as e:
                print(f"Gagal kirim notifikasi ke admin: {e}")
        return

    if intent == "faq_jam":
        await update.message.reply_text(FAQ_JAWABAN["jam"])
        return

    if intent == "faq_lokasi":
        await update.message.reply_text(FAQ_JAWABAN["lokasi"])
        return

    if intent == "faq_harga":
        await update.message.reply_text(FAQ_JAWABAN["harga"])
        return

    try:
        riwayat = get_riwayat_percakapan_user(user_id, limit=5)
        messages_untuk_llm = []
        for pesan_lama, balasan_lama in riwayat:
            messages_untuk_llm.append({"role": "user", "content": pesan_lama})
            messages_untuk_llm.append({"role": "assistant", "content": balasan_lama})
        messages_untuk_llm.append({
            "role": "user",
            "content": f"Jawab pertanyaan berikut HANYA dalam Bahasa Indonesia, jangan gunakan bahasa lain sama sekali: {user_text}"
        })

        response = llm_client.chat.completions.create(
            model="claude-haiku-4-5-20251001",
            messages=messages_untuk_llm
        )
        reply = response.choices[0].message.content

        # Fallback kalau LLM balas kosong
        if not reply or reply.strip() == "":
            reply = "Maaf, saya belum bisa menjawab itu. Bisa coba pertanyaan lain?"

    except Exception as e:
        reply = "Maaf, sedang ada gangguan sistem. Coba lagi dalam beberapa saat ya."
        print(f"Error saat memanggil LLM: {e}")

    save_conversation(
        user_id=str(update.effective_user.id),
        username=update.effective_user.username or "unknown",
        message=user_text,
        reply=reply
    )

    await update.message.reply_text(reply)

# Mulai alur booking
async def booking_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if user_id != admin_id and not is_user_allowed(user_id):
        await update.message.reply_text(
            "Maaf, bot ini masih dalam tahap demo terbatas. Silakan hubungi admin untuk mendapatkan akses. 🙏"
        )
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("💇 Potong Rambut", callback_data="potong_rambut")],
        [InlineKeyboardButton("💆 Pijat/Spa", callback_data="pijat_spa")],
        [InlineKeyboardButton("🚗 Servis Kendaraan", callback_data="servis_kendaraan")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Silakan pilih layanan yang ingin dibooking:",
        reply_markup=reply_markup
    )
    return PILIH_LAYANAN

# User memilih layanan
async def layanan_dipilih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    layanan_map = {
        "potong_rambut": "Potong Rambut",
        "pijat_spa": "Pijat/Spa",
        "servis_kendaraan": "Servis Kendaraan"
    }
    layanan = layanan_map.get(query.data, "Tidak diketahui")
    context.user_data["layanan"] = layanan

    await query.edit_message_text(
        f"Anda memilih: {layanan}\n\nSilakan ketik tanggal booking (format: DD-MM-YYYY), contoh: 25-12-2026"
    )
    return INPUT_TANGGAL

# User mengetik tanggal
async def tanggal_diterima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tanggal_text = update.message.text.strip()

    # Validasi format tanggal DD-MM-YYYY
    try:
        tanggal_obj = datetime.strptime(tanggal_text, "%d-%m-%Y")
    except ValueError:
        await kirim_pesan_aman(
            update,
            "Format tanggal tidak valid. Mohon ketik dengan format DD-MM-YYYY, contoh: 25-12-2026"
        )
        return INPUT_TANGGAL  # pesan error format

    # Validasi tanggal tidak boleh di masa lalu
    if tanggal_obj.date() < datetime.now().date():
        await kirim_pesan_aman(
            update,
            "Tanggal yang Anda masukkan sudah lewat. Mohon pilih tanggal hari ini atau setelahnya."
        )
        return INPUT_TANGGAL

    context.user_data["tanggal"] = tanggal_text
    context.user_data["tanggal"] = tanggal_text
    layanan = context.user_data.get("layanan")

    if not layanan:
        await kirim_pesan_aman(
            update,
            "Sepertinya sesi booking Anda terputus. Mohon mulai ulang dengan mengetik /booking"
        )
        context.user_data.clear()
        return ConversationHandler.END

# Cek ketersediaan jadwal
    jumlah_booking = hitung_booking_pada_tanggal(layanan, tanggal_text)
    if jumlah_booking >= KAPASITAS_PER_HARI:
        await kirim_pesan_aman(
            update,
            f"Mohon maaf, jadwal {layanan} pada tanggal {tanggal_text} sudah penuh "
            f"({jumlah_booking}/{KAPASITAS_PER_HARI} slot terisi).\n\n"
            f"Silakan ketik tanggal lain."
        )
        return INPUT_TANGGAL
    keyboard = [
        [InlineKeyboardButton("✅ Konfirmasi", callback_data="konfirmasi_ya")],
        [InlineKeyboardButton("❌ Batal", callback_data="konfirmasi_batal")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Ringkasan booking Anda:\nLayanan: {layanan}\nTanggal: {tanggal_text}\n\nKonfirmasi booking ini?",
        reply_markup=reply_markup
    )
    return KONFIRMASI

    keyboard = [
        [InlineKeyboardButton("✅ Konfirmasi", callback_data="konfirmasi_ya")],
        [InlineKeyboardButton("❌ Batal", callback_data="konfirmasi_batal")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Ringkasan booking Anda:\nLayanan: {layanan}\nTanggal: {tanggal_text}\n\nKonfirmasi booking ini?",
        reply_markup=reply_markup
    )
    return KONFIRMASI

    keyboard = [
        [InlineKeyboardButton("✅ Konfirmasi", callback_data="konfirmasi_ya")],
        [InlineKeyboardButton("❌ Batal", callback_data="konfirmasi_batal")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Ringkasan booking Anda:\nLayanan: {layanan}\nTanggal: {tanggal}\n\nKonfirmasi booking ini?",
        reply_markup=reply_markup
    )
    return KONFIRMASI

# User konfirmasi atau batal
async def konfirmasi_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "konfirmasi_ya":
        layanan = context.user_data.get("layanan")
        tanggal = context.user_data.get("tanggal")
        user_id = str(update.effective_user.id)
        username = update.effective_user.username or "unknown"

        save_booking(user_id, username, layanan, tanggal)
        tambah_hitungan_booking(user_id)

        await query.edit_message_text(
            f"✅ Booking berhasil dikonfirmasi!\nLayanan: {layanan}\nTanggal: {tanggal}\n\nTerima kasih!"
        )
    else:
        await query.edit_message_text("Booking dibatalkan. Ketik /booking untuk mulai lagi.")

    context.user_data.clear()
    return ConversationHandler.END

# Handler kalau user ketik /cancel di tengah proses booking
async def batal_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Booking dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END
#Handler cancel setelah booking terjadi
async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bookings = get_user_bookings(user_id)

    if not bookings:
        await update.message.reply_text("Anda belum memiliki booking aktif. Ketik /booking untuk membuat booking baru.")
        return

    keyboard = []
    for booking_id, layanan, tanggal in bookings:
        keyboard.append([
            InlineKeyboardButton(
                f"❌ Batal: {layanan} - {tanggal}",
                callback_data=f"cancel_{booking_id}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Booking aktif Anda:\n\nKlik tombol untuk membatalkan booking tertentu.",
        reply_markup=reply_markup
    )

async def cancel_booking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    booking_id = int(query.data.replace("cancel_", ""))
    user_id = str(update.effective_user.id)

    berhasil = cancel_booking(booking_id, user_id)

    if berhasil:
        await query.edit_message_text("✅ Booking berhasil dibatalkan.")
    else:
        await query.edit_message_text("Gagal membatalkan booking. Mungkin sudah dibatalkan sebelumnya.")
async def kirim_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Dipanggil otomatis setiap hari, kirim reminder untuk booking besok"""
    besok = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")
    daftar_booking = get_bookings_untuk_reminder(besok)

    for booking_id, user_id, layanan, tanggal in daftar_booking:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⏰ Pengingat: Anda memiliki booking {layanan} besok ({tanggal}). Sampai jumpa!"
            )
            tandai_sudah_diingatkan(booking_id)
            print(f"Reminder terkirim untuk booking {booking_id}")
        except Exception as e:
            print(f"Gagal kirim reminder untuk booking {booking_id}: {e}")


async def tanggapi_komplain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus admin: /tanggapi <id> <pesan>"""
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    pengirim_id = str(update.effective_user.id)

    if pengirim_id != admin_id:
        await update.message.reply_text("Maaf, perintah ini hanya untuk admin.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Format: /tanggapi <id_komplain> <pesan balasan>")
        return

    try:
        complaint_id = int(args[0])
    except ValueError:
        await update.message.reply_text("ID komplain harus berupa angka.")
        return

    pesan_balasan = " ".join(args[1:])
    komplain = get_complaint(complaint_id)

    if not komplain:
        await update.message.reply_text(f"Komplain dengan ID {complaint_id} tidak ditemukan.")
        return

    _, user_id_pelanggan, username_pelanggan, isi_komplain, status = komplain

    try:
        await context.bot.send_message(
            chat_id=user_id_pelanggan,
            text=f"📩 Tanggapan dari tim kami terkait keluhan Anda:\n\n{pesan_balasan}"
        )
        update_complaint_status(complaint_id, "ditanggapi")
        await update.message.reply_text(f"✅ Tanggapan berhasil dikirim ke pelanggan (komplain ID {complaint_id}).")
    except Exception as e:
        await update.message.reply_text(f"Gagal mengirim tanggapan: {e}")


async def kirim_permintaan_feedback(context: ContextTypes.DEFAULT_TYPE):
    """Dipanggil otomatis setiap hari, minta feedback untuk booking kemarin"""
    kemarin = (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y")
    daftar_booking = get_bookings_untuk_feedback(kemarin)

    for booking_id, user_id, layanan, tanggal in daftar_booking:
        try:
            keyboard = [[
                InlineKeyboardButton("⭐" * i, callback_data=f"rating_{booking_id}_{i}")
                for i in range(1, 6)
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Bagaimana pengalaman Anda dengan layanan {layanan} kemarin? Mohon berikan rating:",
                reply_markup=reply_markup
            )
            tandai_feedback_terkirim(booking_id)
            print(f"Permintaan feedback terkirim untuk booking {booking_id}")
        except Exception as e:
            print(f"Gagal kirim feedback untuk booking {booking_id}: {e}")

async def rating_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangkap klik tombol rating dari user"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    booking_id = int(parts[1])
    rating = int(parts[2])
    user_id = str(update.effective_user.id)

    # Ambil nama layanan dari booking (opsional, bisa juga ambil dari user_data kalau perlu)
    save_rating(booking_id, user_id, "N/A", rating)

    await query.edit_message_text(f"Terima kasih atas rating {'⭐' * rating}-nya! 🙏")


async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus admin: /broadcast <pesan> - kirim ke semua pelanggan"""
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    pengirim_id = str(update.effective_user.id)

    if pengirim_id != admin_id:
        await update.message.reply_text("Maaf, perintah ini hanya untuk admin.")
        return

    if not context.args:
        await update.message.reply_text("Format: /broadcast <pesan pengumuman>")
        return

    pesan_broadcast = " ".join(context.args)
    daftar_customer = get_all_customer_ids()

    if not daftar_customer:
        await update.message.reply_text("Belum ada pelanggan yang tercatat untuk dikirimi broadcast.")
        return

    await update.message.reply_text(f"Mengirim broadcast ke {len(daftar_customer)} pelanggan...")

    berhasil = 0
    gagal = 0

    for customer_id in daftar_customer:
        try:
            await context.bot.send_message(
                chat_id=customer_id,
                text=f"📢 Pengumuman:\n\n{pesan_broadcast}"
            )
            berhasil += 1
            await asyncio.sleep(0.5)  # jeda kecil supaya tidak kena rate limit Telegram
        except Exception as e:
            gagal += 1
            print(f"Gagal kirim broadcast ke {customer_id}: {e}")

    await update.message.reply_text(f"Broadcast selesai. Berhasil: {berhasil}, Gagal: {gagal}")


async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus admin: /export - kirim data booking sebagai file CSV"""
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    pengirim_id = str(update.effective_user.id)

    if pengirim_id != admin_id:
        await update.message.reply_text("Maaf, perintah ini hanya untuk admin.")
        return

    data_booking = get_semua_bookings()

    if not data_booking:
        await update.message.reply_text("Belum ada data booking untuk di-export.")
        return

    # Buat file CSV di memori (tidak perlu simpan ke disk)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "User ID", "Username", "Layanan", "Tanggal", "Status", "Dibuat Pada"])
    for row in data_booking:
        writer.writerow(row)

    # Konversi ke bytes supaya bisa dikirim sebagai file
    output.seek(0)
    file_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    file_bytes.name = f"booking_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    await update.message.reply_document(
        document=file_bytes,
        filename=file_bytes.name,
        caption=f"Data export: {len(data_booking)} booking total"
    )


async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus admin: /export - kirim data booking sebagai file CSV"""
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    pengirim_id = str(update.effective_user.id)

    if pengirim_id != admin_id:
        await update.message.reply_text("Maaf, perintah ini hanya untuk admin.")
        return

    data_booking = get_semua_bookings()

    if not data_booking:
        await update.message.reply_text("Belum ada data booking untuk di-export.")
        return

    # Buat file CSV di memori (tidak perlu simpan ke disk)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "User ID", "Username", "Layanan", "Tanggal", "Status", "Dibuat Pada"])
    for row in data_booking:
        writer.writerow(row)

    # Konversi ke bytes supaya bisa dikirim sebagai file
    output.seek(0)
    file_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    file_bytes.name = f"booking_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    await update.message.reply_document(
        document=file_bytes,
        filename=file_bytes.name,
        caption=f"Data export: {len(data_booking)} booking total"
    )


async def backup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus admin: /backup - kirim file database sebagai dokumen"""
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    pengirim_id = str(update.effective_user.id)

    if pengirim_id != admin_id:
        await update.message.reply_text("Maaf, perintah ini hanya untuk admin.")
        return

    db_path = "chatbot.db"
    if not os.path.exists(db_path):
        await update.message.reply_text("File database tidak ditemukan.")
        return

    nama_backup = f"backup_chatbot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    with open(db_path, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=nama_backup,
            caption=f"Backup database — {datetime.now().strftime('%d %B %Y, %H:%M')} WIB"
        )


async def izinkan_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus admin: /izinkan <user_id> - tambah user ke whitelist"""
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    pengirim_id = str(update.effective_user.id)

    if pengirim_id != admin_id:
        await update.message.reply_text("Maaf, perintah ini hanya untuk admin.")
        return

    if not context.args:
        await update.message.reply_text("Format: /izinkan <user_id>")
        return

    target_user_id = context.args[0]
    add_allowed_user(target_user_id, "unknown")
    await update.message.reply_text(f"✅ User {target_user_id} sekarang diizinkan menggunakan bot.")

async def cabut_izin_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khusus admin: /cabut <user_id> - hapus user dari whitelist"""
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    pengirim_id = str(update.effective_user.id)

    if pengirim_id != admin_id:
        await update.message.reply_text("Maaf, perintah ini hanya untuk admin.")
        return

    if not context.args:
        await update.message.reply_text("Format: /cabut <user_id>")
        return

    target_user_id = context.args[0]
    berhasil = remove_allowed_user(target_user_id)
    if berhasil:
        await update.message.reply_text(f"✅ Akses user {target_user_id} berhasil dicabut.")
    else:
        await update.message.reply_text(f"User {target_user_id} tidak ditemukan di whitelist.")

def main():
    init_db()  # Buat tabel database kalau belum ada
    init_booking_table()
    init_customer_table()
    init_complaint_table()
    init_rating_table()
    init_allowed_users_table()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
# ConversationHandler untuk alur booking
    booking_conv = ConversationHandler(
        entry_points=[CommandHandler("booking", booking_start)],
        states={
            PILIH_LAYANAN: [CallbackQueryHandler(layanan_dipilih)],
            INPUT_TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanggal_diterima)],
            KONFIRMASI: [CallbackQueryHandler(konfirmasi_booking)],
        },
        fallbacks=[CommandHandler("cancel", batal_booking)],
    )
   
    app.add_handler(booking_conv)   
    app.add_handler(CommandHandler("mybookings", my_bookings))
    app.add_handler(CommandHandler("tanggapi", tanggapi_komplain))
    app.add_handler(CommandHandler("broadcast", broadcast_handler))
    app.add_handler(CommandHandler("export", export_handler))
    app.add_handler(CommandHandler("backup", backup_handler))
    app.add_handler(CommandHandler("izinkan", izinkan_user))
    app.add_handler(CommandHandler("cabut", cabut_izin_user))
    app.add_handler(CommandHandler("export", export_handler))
    app.add_handler(CommandHandler("backup", backup_handler))
    app.add_handler(CommandHandler("izinkan", izinkan_user))
    app.add_handler(CommandHandler("cabut", cabut_izin_user))
    app.add_handler(CallbackQueryHandler(cancel_booking_handler, pattern="^cancel_"))
    app.add_handler(CallbackQueryHandler(rating_handler, pattern="^rating_"))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
# Jalankan pengecekan reminder setiap hari jam 09:00
    
    app.job_queue.run_daily(kirim_reminder, time=time(hour=9, minute=0))
    app.job_queue.run_daily(kirim_permintaan_feedback, time=time(hour=10, minute=0))
    print("Bot sedang berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()


