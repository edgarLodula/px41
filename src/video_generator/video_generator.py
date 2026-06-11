import json
import os
import re
import time
import requests

from src.video_generator.slides_generator import gerar_slides

HEYGEN_FALA_MAX_CHARS = 1500   # limite seguro por cena no HeyGen v2


# ─── parsear ──────────────────────────────────────────────────────────────────

def _parsear_cenas(roteiro):
    """
    Divide o roteiro em cenas. Cada cena é um dict com:
      - fala:   texto entre aspas após [AVATAR]
      - visual: descrição após [VISUAL/B-ROLL]  (pode ser None)
      - texto:  texto após [TEXTO NA TELA]       (pode ser None)
    """
    blocos = re.split(r'\[AVATAR\]\s*(?:\(.*?\))?\s*', roteiro, flags=re.DOTALL)
    cenas = []

    for bloco in blocos:
        if not bloco.strip():
            continue

        fala_match = re.search(r'"([^"]+)"', bloco, re.DOTALL)
        if not fala_match:
            continue
        fala = fala_match.group(1).strip().replace('\n', ' ')

        visual_match = re.search(r'\[VISUAL/B-ROLL\]\s*(.+?)(?=\[|$)', bloco, re.DOTALL)
        visual = visual_match.group(1).strip() if visual_match else None

        texto_match = re.search(r'\[TEXTO NA TELA\]\s*(.+?)(?=\[|$)', bloco, re.DOTALL)
        texto = texto_match.group(1).strip() if texto_match else None

        cenas.append({"fala": fala, "visual": visual, "texto": texto})

    return cenas


# ─── upload ───────────────────────────────────────────────────────────────────

def _upload_slides(paths, heygen_token):
    """
    Faz upload de cada PNG para o HeyGen Asset API.
    Retorna list[str] de asset_ids na mesma ordem.
    """
    asset_ids = []
    headers = {"X-Api-Key": heygen_token}

    for path in paths:
        nome = os.path.basename(path)
        with open(path, "rb") as f:
            conteudo = f.read()
        resp = requests.post(
            "https://upload.heygen.com/v1/asset",
            headers={**headers, "Content-Type": "image/png"},
            data=conteudo,
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(
                f"Upload falhou para {nome}: HTTP {resp.status_code} — {resp.text[:300]}"
            )
        data = resp.json().get("data") or {}
        asset_id = data.get("asset_id") or data.get("id")
        if not asset_id:
            raise RuntimeError(
                f"HeyGen Asset nao retornou asset_id para {nome}. "
                f"Resposta completa: {resp.text[:300]}"
            )
        asset_ids.append(asset_id)
        print(f"   Upload OK: {nome} → {asset_id}")

    return asset_ids


# ─── detecção de tipo ─────────────────────────────────────────────────────────

_TALKING_PHOTO_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def _detectar_tipo_character(character_id, heygen_token=None):
    """
    Detecta o tipo do character pelo formato do ID — sem chamada de rede.

    - Hex 32 chars (ex: f232311873f04c73a2a26df1f9cada00) -> talking_photo
    - Qualquer outro formato (descritivo) -> avatar

    heygen_token mantido apenas para compatibilidade da assinatura; não é usado.
    """
    if not character_id or not isinstance(character_id, str):
        raise ValueError(f"character_id invalido: {character_id!r}")
    if _TALKING_PHOTO_ID_RE.match(character_id.strip()):
        return "talking_photo"
    return "avatar"


# ─── preflight ────────────────────────────────────────────────────────────────

def _validar_preflight(character_id, character_type, voice_id, cenas, slide_asset_ids, heygen_token):
    """
    Valida tudo antes de submeter ao HeyGen — sem crédito consumido até aqui.
    Lança ValueError com mensagem clara se algo estiver errado.
    A validação de avatar/talking_photo já foi feita em _detectar_tipo_character.
    """
    headers = {"X-Api-Key": heygen_token}
    erros = []

    # 1. Voice existe na conta?
    try:
        resp = requests.get(
            "https://api.heygen.com/v2/voices",
            headers=headers,
            timeout=15,
        )
        if resp.ok:
            voices = resp.json().get("data", {}).get("voices", [])
            ids_disponiveis = [v.get("voice_id") for v in voices]
            if voice_id not in ids_disponiveis:
                erros.append(
                    f"HEYGEN_VOICE_ID '{voice_id}' nao encontrado na conta.\n"
                    f"   Disponiveis ({len(ids_disponiveis)}): {ids_disponiveis[:8]}"
                )
        else:
            print(f"   [AVISO] Nao foi possivel validar voice_id: HTTP {resp.status_code}")
    except Exception as e:
        print(f"   [AVISO] Falha ao consultar voices: {e}")

    # 2. Cada cena tem fala válida e dentro do limite?
    for i, cena in enumerate(cenas):
        fala = cena.get("fala", "").strip()
        if not fala:
            erros.append(f"Cena {i}: fala vazia.")
        elif len(fala) > HEYGEN_FALA_MAX_CHARS:
            erros.append(
                f"Cena {i}: fala com {len(fala)} chars "
                f"(limite {HEYGEN_FALA_MAX_CHARS}). Será truncada automaticamente."
            )

    # 3. Todos os asset_ids foram preenchidos?
    for i, aid in enumerate(slide_asset_ids):
        if not aid or not isinstance(aid, str):
            erros.append(f"Slide {i}: asset_id invalido ou vazio ({aid!r}).")

    erros_fatais = [e for e in erros if "HEYGEN_VOICE_ID" in e
                    or "fala vazia" in e or "asset_id invalido" in e]
    if erros_fatais:
        raise ValueError("Pre-flight FALHOU — corriga antes de submeter:\n" +
                         "\n".join(f"  • {e}" for e in erros_fatais))

    avisos = [e for e in erros if e not in erros_fatais]
    for a in avisos:
        print(f"   [AVISO] {a}")


# ─── montar input ─────────────────────────────────────────────────────────────

def _montar_video_input(cena, character_id, character_type, voice_id, slide_asset_id=None):
    if character_type == "talking_photo":
        character = {
            "type": "talking_photo",
            "talking_photo_id": character_id,
            "scale": 0.75,
            "offset": {"x": 0.32, "y": 0.05},
        }
    else:
        character = {
            "type": "avatar",
            "avatar_id": character_id,
            "avatar_style": "normal",
            "scale": 0.75,
            "offset": {"x": 0.32, "y": 0.05},
        }

    video_input = {
        "character": character,
        "voice": {
            "type": "text",
            "input_text": cena["fala"].strip()[:HEYGEN_FALA_MAX_CHARS],
            "voice_id": voice_id,
            "speed": 1.0,
        },
    }
    if slide_asset_id:
        video_input["background"] = {
            "type": "image",
            "image_asset_id": slide_asset_id,
        }
    return video_input


# ─── entry point ──────────────────────────────────────────────────────────────

def gerar_video(roteiro, caminho_saida, pasta_slides, disciplina=""):
    token     = os.getenv("HEYGEN_API_KEY")
    avatar_id = os.getenv("HEYGEN_AVATAR_ID")
    voice_id  = os.getenv("HEYGEN_VOICE_ID")

    faltando = [k for k, v in {
        "HEYGEN_API_KEY":   token,
        "HEYGEN_AVATAR_ID": avatar_id,
        "HEYGEN_VOICE_ID":  voice_id,
    }.items() if not v]
    if faltando:
        raise Exception(f"Variáveis de ambiente ausentes no .env: {', '.join(faltando)}")

    # Detectar tipo do character (avatar vs talking_photo)
    print("Detectando tipo do character no HeyGen...")
    character_type = _detectar_tipo_character(avatar_id, token)
    print(f"   Tipo detectado: {character_type}")

    # 1. Parsear cenas
    cenas = _parsear_cenas(roteiro)
    if not cenas:
        raise Exception("Nenhuma cena [AVATAR] encontrada no roteiro.")
    cenas = cenas[:50]

    # 2. Gerar 1 slide por cena
    print(f"Gerando {len(cenas)} slide(s)...")
    slide_paths = gerar_slides(cenas, pasta_slides, disciplina)

    # 3. Upload para HeyGen Assets
    print(f"Fazendo upload de {len(slide_paths)} slide(s) para HeyGen Assets...")
    slide_asset_ids = _upload_slides(slide_paths, token)

    # 4. Contagens
    if not (len(cenas) == len(slide_paths) == len(slide_asset_ids)):
        raise AssertionError(
            f"ERRO: contagens divergem — "
            f"cenas={len(cenas)}, slides={len(slide_paths)}, asset_ids={len(slide_asset_ids)}"
        )

    # 5. Pre-flight — valida tudo ANTES de consumir crédito
    print("Executando validacao pre-flight...")
    _validar_preflight(avatar_id, character_type, voice_id, cenas, slide_asset_ids, token)
    print("   Pre-flight OK.")

    # 6. Montar video_inputs
    video_inputs = [
        _montar_video_input(cenas[i], avatar_id, character_type, voice_id, slide_asset_ids[i])
        for i in range(len(cenas))
    ]

    # Salva payload completo para inspeção
    pasta_debug = os.path.join(os.path.dirname(caminho_saida))
    os.makedirs(pasta_debug, exist_ok=True)
    caminho_payload = os.path.join(pasta_debug, "payload_debug.json")
    with open(caminho_payload, "w", encoding="utf-8") as f:
        json.dump({"video_inputs": video_inputs}, f, indent=2, ensure_ascii=False)
    print(f"Payload completo salvo em: {caminho_payload}")

    print(f"\n[DEBUG] Primeiro video_input (de {len(video_inputs)} total):")
    print(json.dumps(video_inputs[0], indent=2, ensure_ascii=False))
    print()

    # 7. Submeter ao HeyGen v2
    headers = {
        "X-Api-Key": token,
        "Content-Type": "application/json",
    }
    payload = {
        "video_inputs": video_inputs,
        "dimension": {"width": 1280, "height": 720},
    }

    response = requests.post(
        "https://api.heygen.com/v2/video/generate",
        headers=headers,
        json=payload,
    )

    resp_json = response.json()
    data = resp_json.get("data")

    if not data or not data.get("video_id"):
        raise Exception(
            f"HeyGen não retornou video_id. HTTP {response.status_code}. "
            f"Resposta: {resp_json}"
        )

    video_id = data["video_id"]

    # Salva video_id imediatamente — se o polling cair, não precisa re-submeter
    caminho_vid_id = os.path.join(pasta_debug, "video_id.txt")
    with open(caminho_vid_id, "w") as f:
        f.write(video_id)
    print(f"video_id salvo em: {caminho_vid_id}")
    print(f"video_id: {video_id} — aguardando renderizacao...")

    # 8. Polling
    tentativa = 0
    while True:
        time.sleep(10)
        tentativa += 1

        poll_resp = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers=headers,
        )
        poll_json   = poll_resp.json()
        status_data = poll_json.get("data")

        if not status_data:
            raise Exception(
                f"HeyGen não retornou status. HTTP {poll_resp.status_code}. "
                f"Resposta: {poll_json}"
            )

        estado = status_data["status"]
        print(f"   [{tentativa * 10}s] Status: {estado}")

        if estado == "completed":
            video_url   = status_data["video_url"]
            video_bytes = requests.get(video_url, timeout=300).content
            with open(caminho_saida, "wb") as f:
                f.write(video_bytes)
            print(f"   Video salvo em: {caminho_saida}")
            return

        elif estado == "failed":
            raise Exception(
                f"HeyGen falhou durante a renderizacao: {status_data.get('error')}\n"
                f"   video_id preservado em: {caminho_vid_id}"
            )

        elif estado not in ("processing", "pending", "waiting"):
            raise Exception(f"HeyGen retornou status inesperado: {estado}")
