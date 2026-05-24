"""
Lista avatares e vozes disponíveis na conta HeyGen e verifica os IDs configurados.
Custo: ZERO creditos.

Execute com: python scripts/verificar_avatar_heygen.py
"""

import os
import sys
import requests
from dotenv import load_dotenv

DOTENV_PATH = "c:/Users/lizan/OneDrive/Documentos/Atria_Corp/SanMarino/px41/.env"
load_dotenv(DOTENV_PATH)

TOKEN     = os.getenv("HEYGEN_API_KEY", "")
AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID", "")
VOICE_ID  = os.getenv("HEYGEN_VOICE_ID", "")
BASE      = "https://api.heygen.com"

print("=" * 65)
print("VERIFICACAO DE AVATAR E VOZ - HEYGEN")
print("=" * 65)

if not TOKEN:
    print("ERRO: HEYGEN_API_KEY nao encontrada no .env")
    sys.exit(1)

headers = {"X-Api-Key": TOKEN}

# ─── Avatares disponíveis ─────────────────────────────────────────────────────
print(f"\nBuscando avatares (procurando ID: {AVATAR_ID})")

resp = requests.get(
    f"{BASE}/v3/avatars/looks",
    headers=headers,
    params={"limit": 50},
    timeout=15,
)

if not resp.ok:
    print(f"  ERRO HTTP {resp.status_code}: {resp.text[:300]}")
else:
    payload = resp.json()
    looks   = payload.get("data", [])  # retorna lista diretamente

    if not looks:
        print("  Nenhum avatar encontrado na conta.")
    else:
        avatar_encontrado = False
        print(f"  {len(looks)} avatar(s) disponivel(is):\n")
        for look in looks:
            lid    = look.get("id", "")
            nome   = look.get("name", "sem nome")
            tipo   = look.get("avatar_type", "N/A")
            gender = look.get("gender", "")
            engines= ", ".join(look.get("supported_api_engines", []) or [])
            match  = "  <<<  ESTE E O CONFIGURADO NO .env" if lid == AVATAR_ID else ""
            if lid == AVATAR_ID:
                avatar_encontrado = True
            print(f"  Nome    : {nome}")
            print(f"  Tipo    : {tipo}  |  Genero: {gender}")
            print(f"  Engines : {engines}")
            print(f"  ID      : {lid}{match}")
            preview = look.get("preview_image_url") or look.get("preview_video_url")
            if preview:
                print(f"  Preview : {preview}")
            print()

        if not avatar_encontrado:
            print(f"  ATENCAO: HEYGEN_AVATAR_ID do .env NAO encontrado nos avatares desta conta.")
            print(f"  ID configurado : {AVATAR_ID}")
            print(f"  Use um dos IDs listados acima e atualize o .env.")

# ─── Vozes disponíveis ────────────────────────────────────────────────────────
print(f"Buscando vozes (procurando ID: {VOICE_ID})")

resp_v = requests.get(
    f"{BASE}/v3/voices",
    headers=headers,
    params={"limit": 50},
    timeout=15,
)

if not resp_v.ok:
    print(f"  ERRO HTTP {resp_v.status_code}: {resp_v.text[:200]}")
else:
    vdata  = resp_v.json()
    # A API pode retornar lista direta ou dict com "data"
    voices = vdata if isinstance(vdata, list) else vdata.get("data", [])
    if isinstance(voices, dict):
        voices = voices.get("voices", [])

    voz_encontrada = False
    if not voices:
        print("  Nenhuma voz encontrada.")
    else:
        print(f"  {len(voices)} voz(es) disponivel(is) (mostrando primeiras 15):\n")
        for v in voices[:15]:
            vid    = v.get("id", v.get("voice_id", ""))
            nome   = v.get("name", "sem nome")
            idioma = v.get("language", "")
            match  = "  <<<  ESTA E A CONFIGURADA NO .env" if vid == VOICE_ID else ""
            if vid == VOICE_ID:
                voz_encontrada = True
            print(f"  [{idioma:10}] {nome:<35} | {vid}{match}")

        if len(voices) > 15:
            print(f"  ... e mais {len(voices)-15} vozes")

        if not voz_encontrada:
            print(f"\n  ATENCAO: HEYGEN_VOICE_ID do .env NAO encontrado nas primeiras {len(voices)} vozes.")
            print(f"  ID configurado : {VOICE_ID}")

print("\n" + "=" * 65)
