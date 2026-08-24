import os

import requests


def gerar_audio(texto, caminho_saida):
    from gtts import gTTS
    tts = gTTS(text=texto, lang="pt")
    tts.save(caminho_saida)


def gerar_audio_openai_tts(
    texto: str,
    caminho_saida: str,
    openai_token: str | None = None,
    voz: str | None = None,
) -> None:
    """
    Gera áudio MP3 via OpenAI TTS (modelo tts-1).
    Muito mais barato que HeyGen — ideal para narração das cenas de conteúdo.

    Parâmetros
    ----------
    texto         : texto a ser narrado
    caminho_saida : caminho do arquivo MP3 de saída
    openai_token  : chave OpenAI (usa OPENAI_API_KEY do ambiente se omitido)
    voz           : voz OpenAI TTS (usa OPENAI_TTS_VOICE do ambiente ou "nova")
                    Opções: alloy, echo, fable, onyx, nova, shimmer
    """
    from openai import OpenAI

    token = openai_token or os.getenv("OPENAI_API_KEY")
    if not token:
        raise ValueError("OPENAI_API_KEY não configurada.")

    voz_escolhida = voz or os.getenv("OPENAI_TTS_VOICE", "nova")

    client = OpenAI(api_key=token)
    response = client.audio.speech.create(
        model="tts-1",
        voice=voz_escolhida,
        input=texto,
    )
    response.stream_to_file(caminho_saida)


def gerar_audio_heygen_tts(
    texto: str,
    caminho_saida: str,
    heygen_token: str,
    voice_id: str,
    speed: float | None = None,
    locale: str | None = None,
) -> None:
    """
    Gera áudio MP3 via HeyGen Text-to-Speech (POST /v3/voices/speech).

    Usa a MESMA voz configurada para o avatar (ex.: VOZ_FEM_ID/VOZ_MASC_ID),
    mas sem gerar vídeo/avatar — só o áudio. Bem mais barato que gerar um
    vídeo de avatar completo, e evita a robotização da voz OpenAI TTS.
    """
    payload = {"text": texto, "voice_id": voice_id}
    if speed is not None:
        payload["speed"] = speed
    if locale:
        payload["locale"] = locale

    resp = requests.post(
        "https://api.heygen.com/v3/voices/speech",
        headers={"X-Api-Key": heygen_token, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(
            f"HeyGen /v3/voices/speech falhou: HTTP {resp.status_code} — {resp.text[:300]}"
        )

    audio_url = resp.json().get("data", {}).get("audio_url")
    if not audio_url:
        raise RuntimeError(f"HeyGen não retornou audio_url: {resp.text[:300]}")

    audio_resp = requests.get(audio_url, timeout=60)
    audio_resp.raise_for_status()
    with open(caminho_saida, "wb") as f:
        f.write(audio_resp.content)