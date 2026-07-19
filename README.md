# Chatbot Portfolio - Jimmy Faber Aritonang

Bot Telegram sederhana yang terintegrasi dengan LLM (Qwen 2.5 7B via Ollama).

## Fitur
- Command /start dan /help
- Tombol interaktif (inline keyboard)
- Chat bebas dengan AI
- Fallback handling untuk error

## Tech Stack
- Python
- python-telegram-bot
- FastAPI
- Ollama (Qwen 2.5 7B)


## WhatsApp Bot
Bot WhatsApp yang terintegrasi dengan WhatsApp Cloud API (Meta), mendukung:
- Webhook untuk menerima pesan real-time
- Integrasi LLM (Qwen 2.5 7B) untuk balasan otomatis
- Message status tracking (sent/delivered/failed)
- Teruji end-to-end dengan pemahaman terhadap keterbatasan kebijakan regional Meta pada akun test

## Booking Flow (Dialogue State Management)
Fitur pemesanan/booking dengan alur percakapan bertahap di Bot Telegram, menggunakan `ConversationHandler`:

1. User ketik `/booking`
2. Bot menampilkan pilihan layanan (tombol interaktif)
3. User memilih layanan → bot meminta tanggal
4. User mengetik tanggal → bot menampilkan ringkasan untuk konfirmasi
5. User konfirmasi → data tersimpan ke database
6. User bisa membatalkan proses kapan saja dengan `/cancel`

Ini mendemonstrasikan kemampuan mengelola **dialogue state** (bot mengingat tahap percakapan user) dan **fallback handling**, relevan untuk use case seperti appointment booking dan order taking.

### Contoh Alur
```
/booking → Pilih layanan → Input tanggal → Konfirmasi → Tersimpan di database
```

### Tech Stack Tambahan
- FastAPI (webhook receiver)
- httpx (async HTTP client)
- ngrok (tunnel untuk testing lokal)
