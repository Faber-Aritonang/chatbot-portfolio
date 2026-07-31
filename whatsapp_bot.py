import os
import httpx
from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from openai import OpenAI
from database import init_processed_messages_table, sudah_diproses, tandai_sudah_diproses

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = "jimmy_verify_123"  # bebas, nanti dipakai saat setup webhook di dashboard Meta

app = FastAPI()
init_processed_messages_table()

llm_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

# Endpoint verifikasi webhook (dipanggil Meta sekali saat setup)
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
):
    if hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)
    return PlainTextResponse(content="Verifikasi gagal", status_code=403)

# Endpoint menerima pesan masuk
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("Payload masuk:", data)

    try:
        entry = data["entry"][0]
        change = entry["changes"][0]["value"]

        if "messages" in change:
            message = change["messages"][0]
            message_id = message.get("id")

            # Cegah pemrosesan duplikat (WhatsApp bisa kirim event yang sama 2x)
            if message_id and sudah_diproses(message_id):
                print(f"Pesan {message_id} sudah pernah diproses, dilewati.")
                return {"status": "ok"}

            from_number = message["from"]
            text = message["text"]["body"]

            if message_id:
                tandai_sudah_diproses(message_id)

            print(f"Pesan dari {from_number}: {text}")

            # Kirim ke LLM untuk dapat balasan
            response = llm_client.chat.completions.create(
                model="qwen2.5:7b",
                messages=[{"role": "user", "content": text}]
            )
            reply = response.choices[0].message.content

            # Kirim balasan lewat WhatsApp API
            await send_whatsapp_message(from_number, reply)

    except (KeyError, IndexError) as e:
        print(f"Bukan pesan teks atau format tidak dikenali: {e}")

    return {"status": "ok"}

# Fungsi untuk kirim pesan lewat WhatsApp Cloud API
async def send_whatsapp_message(to_number: str, message: str):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message}
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        print("Status kirim WhatsApp:", response.status_code, response.text)
