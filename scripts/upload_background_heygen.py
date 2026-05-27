"""
Upload do background para o HeyGen como asset permanente.

Executa UMA VEZ para registrar a imagem na plataforma HeyGen
e salva o asset_id no .env automaticamente.

Execute com: python scripts/upload_background_heygen.py
"""

import os
import sys
import uuid
import requests
from dotenv import load_dotenv, set_key

DOTENV_PATH = "c:/Users/lizan/OneDrive/Documentos/Atria_Corp/SanMarino/px41/.env"
IMAGEM_PATH = "c:/Users/lizan/OneDrive/Documentos/Atria_Corp/SanMarino/px41/assets/background_avatar.png"

load_dotenv(DOTENV_PATH)

token = os.getenv("HEYGEN_API_KEY")

if not token:
    print("ERRO: HEYGEN_API_KEY nao encontrada no .env")
    sys.exit(1)

# Verifica se ja existe asset_id salvo
asset_id_existente = os.getenv("HEYGEN_BG_ASSET_ID")
if asset_id_existente:
    print(f"Asset ja registrado: {asset_id_existente}")
    print("Nada a fazer. Para re-enviar, remova HEYGEN_BG_ASSET_ID do .env e rode novamente.")
    sys.exit(0)

if not os.path.exists(IMAGEM_PATH):
    print(f"ERRO: imagem nao encontrada em: {IMAGEM_PATH}")
    sys.exit(1)

tamanho_mb = os.path.getsize(IMAGEM_PATH) / (1024 * 1024)
print(f"Imagem: {IMAGEM_PATH}")
print(f"Tamanho: {tamanho_mb:.2f} MB (limite HeyGen: 32 MB)")

print("\nEnviando para HeyGen...")

with open(IMAGEM_PATH, "rb") as f:
    resp = requests.post(
        "https://api.heygen.com/v3/assets",
        headers={
            "X-Api-Key":      token,
            "Idempotency-Key": str(uuid.uuid4()),
        },
        files={"file": ("background_avatar.png", f, "image/png")},
        timeout=60,
    )

if not resp.ok:
    print(f"ERRO: HTTP {resp.status_code}")
    print(resp.text[:300])
    sys.exit(1)

data     = resp.json().get("data", {})
asset_id = data.get("asset_id")
url      = data.get("url")

print(f"\nUpload concluido!")
print(f"  asset_id : {asset_id}")
print(f"  url      : {url}")
print(f"  mime     : {data.get('mime_type')}")
print(f"  tamanho  : {data.get('size_bytes', 0) / 1024:.1f} KB")

# Salva no .env automaticamente
set_key(DOTENV_PATH, "HEYGEN_BG_ASSET_ID", asset_id)
print(f"\nHEYGEN_BG_ASSET_ID salvo no .env: {asset_id}")
print("O background sera usado automaticamente na proxima geracao de video.")
