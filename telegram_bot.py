import asyncio
from telegram.error import TimedOut, NetworkError
from datetime import datetime
from database import init_db, save_conversation, init_booking_table, save_booking, hitung_booking_pada_tanggal, get_user_bookings, cancel_booking, get_bookings_untuk_reminder, tandai_sudah_diingatkan, init_customer_table, upsert_customer, get_customer, tambah_hitungan_booking
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
    base_url="http://localhost:11434/v1",
    api_key="ollama"
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
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    # Fallback sederhana: kalau pesan terlalu pendek/tidak jelas
    if len(user_text.strip()) < 2:
        await update.message.reply_text("Pesan Anda terlalu pendek, coba tulis lebih lengkap ya 🙂")
        return

    try:
        response = llm_client.chat.completions.create(
            model="qwen2.5:7b",
            messages=[{"role": "user", "content": user_text}]
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

# Mulai alur booking
async def booking_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

def main():
    init_db()  # Buat tabel database kalau belum ada
    init_booking_table()
    init_customer_table()
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
    app.add_handler(CallbackQueryHandler(cancel_booking_handler, pattern="^cancel_"))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
# Jalankan pengecekan reminder setiap hari jam 09:00
    
    app.job_queue.run_daily(kirim_reminder, time=time(hour=9, minute=0))
    print("Bot sedang berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()


