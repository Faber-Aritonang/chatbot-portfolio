from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

# Skema data yang diterima dari request
class ChatRequest(BaseModel):
    message: str

@app.get("/")
def home():
    return {"status": "Server jalan!"}

@app.post("/chat")
def chat(request: ChatRequest):
    response = client.chat.completions.create(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": request.message}]
    )
    reply = response.choices[0].message.content
    return {"reply": reply}
