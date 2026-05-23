import os
import re
import time
import requests


def _parsear_cenas(roteiro):
    """
    Divide o roteiro em cenas. Cada cena é um dict com:
      - fala:   texto entre aspas após [AVATAR]
      - visual: descrição após [VISUAL/B-ROLL]  (pode ser None)
      - texto:  texto após [TEXTO NA TELA]       (pode ser None)
    """
    # Divide nos blocos [AVATAR] — cada bloco inicia uma nova cena
    blocos = re.split(r'\[AVATAR\]\s*(?:\(.*?\))?\s*', roteiro, flags=re.DOTALL)
    cenas = []

    for bloco in blocos:
        if not bloco.strip():
            continue

        # Extrai somente o texto entre as primeiras aspas duplas
        fala_match = re.search(r'"([^"]+)"', bloco, re.DOTALL)
        if not fala_match:
            continue
        fala = fala_match.group(1).strip().replace('\n', ' ')

        # Extrai o primeiro parágrafo após [VISUAL/B-ROLL]
        visual_match = re.search(r'\[VISUAL/B-ROLL\]\s*(.+?)(?=\[|$)', bloco, re.DOTALL)
        visual = visual_match.group(1).strip() if visual_match else None

        # Extrai o primeiro parágrafo após [TEXTO NA TELA]
        texto_match = re.search(r'\[TEXTO NA TELA\]\s*(.+?)(?=\[|$)', bloco, re.DOTALL)
        texto = texto_match.group(1).strip() if texto_match else None

        cenas.append({"fala": fala, "visual": visual, "texto": texto})

    return cenas


def _montar_video_input(cena, avatar_id, voice_id):
    video_input = {
        "character": {
            "type": "avatar",
            "avatar_id": avatar_id,
            "avatar_style": "normal"
        },
        "voice": {
            "type": "text",
            "input_text": cena["fala"][:5000],
            "voice_id": voice_id,
            "speed": 1.0
        }
    }

    if cena["visual"]:
        video_input["background"] = {
            "type": "color",
            "value": "#000000"
            # Para suportar imagem/vídeo real, substitua por:
            # "type": "image", "url": <url_da_imagem>
        }

    if cena["texto"]:
        video_input["text"] = {
            "type": "text",
            "text": cena["texto"],
            "font_family": "Arial",
            "font_size": 32,
            "color": "#FFFFFF",
            "position": "bottom",
            "text_align": "center",
            "line_height": 1.5
        }

    return video_input


def gerar_video(roteiro, caminho_saida):
    token = os.getenv("HEYGEN_API_KEY")
    avatar_id = os.getenv("HEYGEN_AVATAR_ID")
    voice_id = os.getenv("HEYGEN_VOICE_ID")

    faltando = [k for k, v in {
        "HEYGEN_API_KEY": token,
        "HEYGEN_AVATAR_ID": avatar_id,
        "HEYGEN_VOICE_ID": voice_id
    }.items() if not v]
    if faltando:
        raise Exception(f"Variáveis de ambiente ausentes no .env: {', '.join(faltando)}")

    cenas = _parsear_cenas(roteiro)
    if not cenas:
        raise Exception("Nenhuma cena [AVATAR] encontrada no roteiro.")

    # A API aceita até 50 video_inputs por requisição
    cenas = cenas[:50]

    headers = {
        "X-Api-Key": token,
        "Content-Type": "application/json"
    }

    payload = {
        "video_inputs": [_montar_video_input(c, avatar_id, voice_id) for c in cenas],
        "dimension": {"width": 1280, "height": 720}
    }

    response = requests.post(
        "https://api.heygen.com/v2/video/generate",
        headers=headers,
        json=payload
    )

    resp_json = response.json()
    data = resp_json.get("data")

    if not data or not data.get("video_id"):
        raise Exception(
            f"HeyGen não retornou video_id. HTTP {response.status_code}. "
            f"Resposta: {resp_json}"
        )

    video_id = data["video_id"]

    tentativa = 0
    while True:
        time.sleep(10)
        tentativa += 1

        poll_resp = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers=headers
        )
        poll_json = poll_resp.json()
        status_data = poll_json.get("data")

        if not status_data:
            raise Exception(
                f"HeyGen não retornou status. HTTP {poll_resp.status_code}. "
                f"Resposta: {poll_json}"
            )

        estado = status_data["status"]
        print(f"   ⏳ [{tentativa * 10}s] Status: {estado}")

        if estado == "completed":
            video_url = status_data["video_url"]
            video_bytes = requests.get(video_url, timeout=300).content
            with open(caminho_saida, "wb") as f:
                f.write(video_bytes)
            print(f"   ✅ Vídeo salvo em: {caminho_saida}")
            return

        elif estado == "failed":
            raise Exception(f"HeyGen falhou: {status_data.get('error')}")

        elif estado not in ("processing", "pending", "waiting"):
            raise Exception(f"HeyGen retornou status inesperado: {estado}")
