import os
import requests
import time

def gerar_video(roteiro, caminho_saida):
    token = os.getenv("HEYGEN_API_KEY")
    avatar_id = os.getenv("HEYGEN_AVATAR_ID")
    voice_id = os.getenv("HEYGEN_VOICE_ID")

    faltando = [k for k, v in {"HEYGEN_API_KEY": token, "HEYGEN_AVATAR_ID": avatar_id, "HEYGEN_VOICE_ID": voice_id}.items() if not v]
    if faltando:
        raise Exception(f"Variáveis de ambiente ausentes no .env: {', '.join(faltando)}")

    headers = {
        "X-Api-Key": token,
        "Content-Type": "application/json"
    }

    # 1. Criar vídeo
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": roteiro[:5000],
                    "voice_id": voice_id,
                    "speed": 1.0
                }
            }
        ],
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

    # 2. Polling
    for _ in range(30):
        time.sleep(10)

        poll_resp = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers=headers
        )
        poll_json = poll_resp.json()
        status = poll_json.get("data")

        if not status:
            raise Exception(
                f"HeyGen não retornou status. HTTP {poll_resp.status_code}. "
                f"Resposta: {poll_json}"
            )

        if status["status"] == "completed":
            # 3. Download
            video_url = status["video_url"]
            video_bytes = requests.get(video_url).content
            with open(caminho_saida, "wb") as f:
                f.write(video_bytes)
            print(f"   ✅ Vídeo salvo em: {caminho_saida}")
            return

        elif status["status"] == "failed":
            raise Exception(f"HeyGen falhou: {status.get('error')}")

    raise TimeoutError("Timeout: vídeo não ficou pronto em 5 minutos.")