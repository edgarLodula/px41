import os
import sys
from dotenv import load_dotenv
import requests

load_dotenv("c:/Users/lizan/OneDrive/Documentos/Atria_Corp/SanMarino/px41/.env")

key   = os.getenv("GEMINI_API_KEY", "")
model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

print("=" * 50)
print("TESTE DE CHAVE GEMINI")
print("=" * 50)
print(f"Chave carregada : {'SIM' if key else 'NÃO'}")
print(f"Primeiros chars : {key[:8] + '...' if key else 'VAZIA'}")
print(f"Comprimento     : {len(key)} chars")
print(f"Modelo          : {model}")
print()

if not key:
    print("❌ GEMINI_API_KEY está vazia no .env!")
    sys.exit(1)

print("Fazendo chamada de teste...")
resp = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
    headers={"Content-Type": "application/json"},
    json={"contents": [{"parts": [{"text": "Responda apenas com a palavra: OK"}]}],
          "generationConfig": {"maxOutputTokens": 10}},
    timeout=15,
)

print(f"HTTP Status : {resp.status_code}")

if resp.status_code == 200:
    texto = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    print(f"Resposta    : {texto}")
    print("\n✅ Gemini funcionando corretamente!")
elif resp.status_code == 400:
    print(f"❌ Requisição inválida: {resp.text[:400]}")
elif resp.status_code == 403:
    data = resp.json()
    print("ACESSO NEGADO (403)")
    print(f"   Mensagem : {data.get('error', {}).get('message', resp.text[:400])}")
    print(f"   Status   : {data.get('error', {}).get('status', '')}")
    print()
    print("Causas possiveis:")
    print("  1. Chave incorreta ou expirada")
    print("  2. API 'Generative Language' nao habilitada no projeto Google Cloud")
    print("  3. Billing nao ativo no projeto")
    print("  -> Verifique em: https://aistudio.google.com/app/apikey")
elif resp.status_code == 429:
    print("RATE LIMIT. Aguarde e tente novamente.")
else:
    print(f"ERRO INESPERADO: {resp.text[:300]}")
