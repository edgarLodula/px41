"""
Lista avatares e voices disponíveis na conta HeyGen.
Execute: python listar_avatars.py
"""

import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("HEYGEN_API_KEY")
if not token:
    print("ERRO: HEYGEN_API_KEY nao encontrada no .env")
    exit(1)

headers = {"X-Api-Key": token}

UUID_RE = re.compile(r'^[0-9a-f]{32}$', re.I)


def _e_uuid(avatar_id: str) -> bool:
    return bool(UUID_RE.match(avatar_id.replace("-", "")))


# ── Avatares ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("AVATARES DISPONÍVEIS")
print("=" * 70)

resp = requests.get("https://api.heygen.com/v2/avatars", headers=headers, timeout=15)
if not resp.ok:
    print(f"Erro: HTTP {resp.status_code} — {resp.text[:200]}")
else:
    avatars = resp.json().get("data", {}).get("avatars", [])

    publicos  = [a for a in avatars if not _e_uuid(a.get("avatar_id", ""))]
    privados  = [a for a in avatars if     _e_uuid(a.get("avatar_id", ""))]

    print(f"\n  ✅ PUBLICOS (nome-texto) — use estes, funcionam em qualquer conta ({len(publicos)})")
    for a in publicos:
        aid    = a.get("avatar_id", "?")
        nome   = a.get("avatar_name", "?")
        gender = a.get("gender", "?")
        print(f"    {aid:<48}  {nome:<30}  {gender}")

    if privados:
        print(f"\n  ⚠️  UUID / customizados — podem nao funcionar fora do workspace original ({len(privados)})")
        for a in privados[:10]:
            aid    = a.get("avatar_id", "?")
            nome   = a.get("avatar_name", "?")
            print(f"    {aid:<48}  {nome}")
        if len(privados) > 10:
            print(f"    ... e mais {len(privados) - 10} omitidos")

# ── Voices ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("VOICES DISPONÍVEIS  (português em primeiro)")
print("=" * 70)

resp = requests.get("https://api.heygen.com/v2/voices", headers=headers, timeout=15)
if not resp.ok:
    print(f"Erro: HTTP {resp.status_code} — {resp.text[:200]}")
else:
    voices = resp.json().get("data", {}).get("voices", [])

    por_idioma: dict[str, list] = {}
    for v in voices:
        lang = v.get("language") or v.get("locale") or "?"
        por_idioma.setdefault(lang, []).append(v)

    prio = ["portuguese", "pt-br", "pt"]
    idiomas = sorted(
        por_idioma.keys(),
        key=lambda x: (0 if any(p in x.lower() for p in prio) else 1, x)
    )

    for lang in idiomas:
        print(f"\n  [{lang}]")
        for v in por_idioma[lang]:
            vid    = v.get("voice_id", "?")
            nome   = v.get("display_name") or v.get("name", "?")
            gender = v.get("gender", "?")
            print(f"    {vid:<48}  {nome:<30}  {gender}")

print("\n" + "=" * 70)
print("Escolha um avatar PUBLICO e copie para o .env:")
print("  HEYGEN_AVATAR_ID=<avatar_id do bloco PUBLICOS acima>")
print("  HEYGEN_VOICE_ID=<voice_id>")
print("=" * 70 + "\n")
