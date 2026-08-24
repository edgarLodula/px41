import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("HEYGEN_API_KEY")

if not api_key:
    raise RuntimeError("HEYGEN_API_KEY não configurada no arquivo .env.")

response = requests.get(
    "https://api.heygen.com/v3/voices",
    headers={
        "X-Api-Key": api_key,
    },
    params={
        "engine": "starfish",
        "limit": 100,
    },
    timeout=30,
)

if not response.ok:
    raise RuntimeError(
        f"Erro ao listar vozes: HTTP {response.status_code} — "
        f"{response.text}"
    )

payload = response.json()
vozes = payload.get("data", [])

# Algumas respostas podem colocar os resultados dentro de "voices".
if isinstance(vozes, dict):
    vozes = vozes.get("voices", [])

print(f"\nTotal de vozes Starfish encontradas: {len(vozes)}\n")

for voz in vozes:
    idioma = str(
        voz.get("language")
        or voz.get("locale")
        or ""
    ).lower()

    if any(termo in idioma for termo in ("portugu", "pt-br", "brazil")):
        print("=" * 70)
        print(f"Nome: {voz.get('name', 'Não informado')}")
        print(f"ID: {voz.get('voice_id', 'Não informado')}")
        print(f"Gênero: {voz.get('gender', 'Não informado')}")
        print(f"Idioma: {voz.get('language') or voz.get('locale')}")
        print(f"Engine: {voz.get('engine', 'starfish')}")
        print(
            "Preview:",
            voz.get("preview_audio_url")
            or voz.get("preview_url")
            or "Não disponível",
        )