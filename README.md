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

### Tech Stack Tambahan
- FastAPI (webhook receiver)
- httpx (async HTTP client)
- ngrok (tunnel untuk testing lokal)
