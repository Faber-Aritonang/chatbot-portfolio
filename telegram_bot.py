from database import init_db, save_conversation
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI

# Muat variabel dari .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup koneksi ke Qwen lewat Ollama
llm_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

# Handler untuk command /start - sekarang dengan tombol interaktif
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💬 Chat Bebas", callback_data="chat_bebas")],
        [InlineKeyboardButton("ℹ️ Tentang Bot", callback_data="tentang")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Halo! Saya bot Si Dodol. Pilih menu di bawah atau langsung ketik pesan bebas:",
        reply_markup=reply_markup
    )

# Handler saat tombol di-klik
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # wajib ada, supaya tombol tidak "loading" terus

    if query.data == "chat_bebas":
        await query.edit_message_text("Silakan ketik pertanyaan Anda, saya akan coba jawab 🙂")
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

# Main function untuk jalankan bot
def main():
    init_db()  # Buat tabel database kalau belum ada
    app = Application.builder().token(TELEGRAM_TOKEN).build()
      
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot sedang berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()

