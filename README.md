# Chatbot Portfolio — Jimmy Faber

Bot Telegram dan WhatsApp yang terintegrasi dengan LLM (Qwen 2.5 7B via Ollama), dengan fitur booking/appointment lengkap: dialogue state management, validasi input, cek ketersediaan jadwal, manajemen booking, dan reminder otomatis.

Coba Langsung: Bot Telegram — t.me/sidodol_chatbot_bot (live 24/7, di-deploy di Render)

## Riwayat Versi

| Versi | Fitur |
|---|---|
| v1.0 | Bot dasar Telegram & WhatsApp, integrasi LLM, booking flow sederhana (dialogue state) |
| v1.1 | Validasi format & tanggal lewat, retry logic untuk gangguan jaringan, pengaman data booking tidak lengkap |
| v1.2 | Cek ketersediaan jadwal — kapasitas maksimal booking per layanan per tanggal |
| v1.3 | Fitur /mybookings — lihat dan batalkan booking aktif, dengan validasi kepemilikan user |
| v1.4 | Reminder otomatis — notifikasi H-1 sebelum jadwal booking via job scheduler |
| v2.0 | Evolusi menjadi Customer Relation Service (CRS): profil pelanggan (bot mengenali pelanggan lama), deteksi intent sederhana (FAQ/booking/komplain) |
| v2.1 | Eskalasi komplain ke admin: notifikasi otomatis saat ada keluhan baru, admin dapat membalas langsung via /tanggapi |
| v2.2 | Konteks percakapan: bot menyertakan riwayat chat sebelumnya saat memanggil LLM untuk respons yang lebih koheren |
| v2.3 | Feedback/rating: bot otomatis minta rating bintang 1-5 sehari setelah jadwal booking selesai |
| v2.4 | Broadcast: admin dapat mengirim pengumuman ke seluruh pelanggan terdaftar via /broadcast |
| v2.5 | Export data: admin dapat mengunduh seluruh data booking sebagai file CSV via /export |
| v2.6 | Rate limiting: mencegah spam dengan batas maksimal 5 pesan per menit per user |
| v2.7 | Deduplikasi pesan WhatsApp: cegah pemrosesan ganda menggunakan message_id tracking |
| v2.8 | Backup database: admin dapat mengunduh salinan database via /backup |
| v3.0 | Migrasi LLM dari Qwen lokal ke Claude Haiku 4.5 (Anthropic): konsistensi bahasa terjamin, kualitas respons lebih baik, siap deployment produksi |
| v3.1 | Sistem whitelist: kontrol akses user via /izinkan dan /cabut, penting untuk deployment demo dengan budget token terkendali |
| v3.2 | Deploy sukses ke Render (free tier): bot Telegram hidup 24/7 via webhook, terverifikasi berfungsi end-to-end di server produksi |
| v3.3 | Dashboard analitik dengan grafik interaktif (Chart.js): ringkasan bisnis, layanan terpopuler, tren booking, rating, status komplain — terverifikasi real-time di production |

Lihat riwayat lengkap di GitHub Releases/Tags: https://github.com/Faber-Aritonang/chatbot-portfolio/tags

## Fitur

### Telegram Bot
- Command handling (/start, /help, /booking, /mybookings, /cancel)
- Tombol interaktif (inline keyboard)
- Chat bebas dengan AI (LLM)
- Booking flow dengan dialogue state (ConversationHandler):
  1. /booking -> pilih layanan -> input tanggal -> konfirmasi -> tersimpan ke database
  2. Validasi format tanggal (DD-MM-YYYY) dan penolakan tanggal yang sudah lewat
  3. Cek ketersediaan jadwal - booking ditolak otomatis kalau kapasitas harian penuh
  4. /mybookings - lihat booking aktif dan batalkan kapan saja
  5. Reminder otomatis dikirim H-1 sebelum jadwal
- Retry logic otomatis untuk gangguan jaringan saat mengirim pesan
- Fallback handling untuk input tidak valid, error LLM, dan sesi yang terputus

### WhatsApp Bot
- Webhook receiver menggunakan FastAPI, tunneling via ngrok untuk pengembangan lokal
- Integrasi LLM (Qwen 2.5 7B) untuk balasan otomatis
- Message status tracking (sent/delivered/failed)
- Catatan jujur: Teruji end-to-end untuk penerimaan pesan dan pemrosesan webhook. Pengiriman keluar ke nomor Indonesia saat ini terblokir oleh kebijakan cross-border messaging Meta (error 130497) pada nomor uji coba (sandbox) - ini keterbatasan kebijakan platform, bukan keterbatasan kode.

## Riwayat Pemilihan LLM

Bot ini awalnya dikembangkan menggunakan Qwen 2.5 7B (via Ollama, lokal) untuk pengembangan tanpa biaya. Sebagai model open-source berukuran kecil, model tersebut sesekali mencampur bahasa pada topik kompleks — bukan bug kode, melainkan keterbatasan bawaan model kecil.

Sejak v3.0, bot ini bermigrasi ke **Claude Haiku 4.5 (Anthropic)** untuk kualitas dan konsistensi respons yang lebih baik, sekaligus mempersiapkan bot untuk deployment produksi 24/7. Migrasi ini hanya memerlukan perubahan `base_url`, API key, dan nama model — arsitektur kode lainnya tidak berubah, menunjukkan desain yang fleksibel untuk berpindah antar penyedia LLM.

## Tech Stack

- Bahasa: Python
- Bot Framework: python-telegram-bot (dengan ConversationHandler untuk dialogue state, JobQueue untuk scheduler)
- Web Framework: FastAPI (webhook receiver untuk WhatsApp)
- HTTP Client: httpx (async)
- LLM: Qwen 2.5 7B (lokal via Ollama) - kompatibel dengan OpenAI/Anthropic API untuk deployment produksi
- Database: SQLite (riwayat percakapan, data booking)
- Tunneling: ngrok (untuk pengembangan webhook lokal)

## Strategi Akses Terbatas (Demo Mode)

Bot ini menerapkan sistem whitelist untuk mengontrol siapa saja yang bisa menggunakan fitur AI-nya — penting saat bot di-deploy publik (24/7) namun masih menggunakan budget token pribadi untuk keperluan presentasi produk, bukan operasional bisnis penuh.

- User baru yang belum diizinkan akan menerima pesan "demo terbatas, hubungi admin"
- Admin dapat menambahkan akses dengan `/izinkan <user_id>` dan mencabutnya dengan `/cabut <user_id>`
- Pendekatan ini memungkinkan bot didemokan ke calon klien secara terkendali tanpa risiko penyalahgunaan token API

## Setup

python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn python-telegram-bot[job-queue] httpx python-dotenv openai
cp .env.example .env
python3 telegram_bot.py

## Struktur Proyek

chatbot-portfolio/
- telegram_bot.py      : Bot Telegram lengkap dengan booking flow
- whatsapp_bot.py      : Webhook receiver untuk WhatsApp Cloud API
- server.py            : FastAPI bridge dasar
- database.py          : Modul database SQLite (conversations & bookings)
- test_llm.py          : Script test koneksi LLM standalone
- README.md

## Roadmap Pengembangan Selanjutnya

- Dashboard analisis data booking (layanan terpopuler, jam/hari tersibuk)
- Notifikasi ke admin/pemilik bisnis setiap ada booking baru
- Deduplikasi pesan WhatsApp berbasis message ID
- Deployment ke cloud (Render/Railway) dengan LLM cloud API untuk akses 24/7

## Kontak

Jimmy Faber - faber.aritonang@gmail.com
LinkedIn: linkedin.com/in/jimmyfaber-7ab463279
