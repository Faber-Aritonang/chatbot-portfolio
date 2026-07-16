from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

while True:
    user_input = input("Anda: ")
    if user_input.lower() in ["exit", "keluar"]:
        break
    
    response = client.chat.completions.create(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": user_input}]
    )
    
    print("Si_Dodol:", response.choices[0].message.content)
