"""
Legendas para os vídeos finais (avatar + slide já compostos).

Por que transcrever em vez de estimar por tempo/caracteres:
  A HeyGen tem um recurso nativo de legenda (`caption` em POST /v3/videos),
  mas é um recurso premium (Enterprise) e, mesmo com acesso, só legendaria o
  clipe isolado do avatar — o vídeo final daqui é composto localmente
  (avatar + slide, via compor_avatar_slides.py), então a legenda da HeyGen
  nunca veria o resultado final.

  Em vez de estimar o tempo de cada frase dividindo a duração da cena pela
  contagem de caracteres (impreciso — não captura pausas nem ritmo real da
  fala), transcrevemos o áudio de verdade com o Whisper da OpenAI (já é
  dependência do projeto), que devolve timestamps reais.

Fluxo:
  1. Extrai o áudio do vídeo final (ffmpeg).
  2. Transcreve com Whisper, pedindo a saída já em .srt.
  3. Queima o .srt no vídeo com o filtro `subtitles` do ffmpeg (libass).

Requer ffmpeg no PATH (compilado com libass, o padrão do build "full" do
gyan.dev/BtbN já inclui).
"""

import os
import subprocess

from openai import OpenAI

# ─── ESTILO DA LEGENDA (combina com a identidade visual "lousa" dos slides) ───
LEGENDA_FONTE       = "Arial"
LEGENDA_TAMANHO     = 20
LEGENDA_COR_TEXTO   = "&H00E8E8E8"   # branco giz (BGR invertido, ASS)
LEGENDA_COR_FUNDO   = "&H80000000"   # preto ~50% opaco (caixa atrás do texto)
LEGENDA_MARGEM_V    = 28             # distância da borda inferior (px)
LEGENDA_MARGEM_LR   = 40             # margem lateral (px)
# ───────────────────────────────────────────────────────────────────────────────


def _extrair_audio(caminho_video: str, caminho_audio: str):
    r = subprocess.run(
        [
            "ffmpeg", "-y", "-i", caminho_video,
            "-vn", "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1", "-b:a", "64k",
            caminho_audio,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg (extração de áudio) falhou: {r.stderr[-500:]}")


def transcrever_srt(caminho_video: str, caminho_srt: str, openai_token: str,
                     prompt_contexto: str = "") -> str:
    """
    Extrai o áudio do vídeo e transcreve com Whisper, salvando um .srt com
    timestamps reais da fala. Retorna o caminho do .srt gerado.

    `prompt_contexto` (opcional): termos técnicos/nomes próprios da disciplina
    para ajudar o Whisper a acertar a grafia (ex.: siglas, jargão técnico).
    """
    client = OpenAI(api_key=openai_token)
    pasta_temp = os.path.dirname(os.path.abspath(caminho_srt)) or "."
    caminho_audio = os.path.join(pasta_temp, "_audio_transcricao_tmp.mp3")
    _extrair_audio(caminho_video, caminho_audio)

    try:
        with open(caminho_audio, "rb") as f:
            kwargs = {
                "model": "whisper-1",
                "file": f,
                "language": "pt",
                "response_format": "srt",
            }
            if prompt_contexto:
                kwargs["prompt"] = prompt_contexto[:800]
            resposta = client.audio.transcriptions.create(**kwargs)
    finally:
        if os.path.isfile(caminho_audio):
            os.remove(caminho_audio)

    texto_srt = resposta if isinstance(resposta, str) else str(resposta)
    with open(caminho_srt, "w", encoding="utf-8") as f:
        f.write(texto_srt)
    return caminho_srt


def _escapar_caminho_ffmpeg(caminho: str) -> str:
    """Escapa um caminho absoluto para uso dentro de -vf no ffmpeg (Windows: 'C:\\...')."""
    caminho = os.path.abspath(caminho).replace("\\", "/")
    return caminho.replace(":", "\\:")


def queimar_legenda(caminho_video: str, caminho_srt: str, caminho_saida: str):
    """Queima o .srt no vídeo, no rodapé central (largura toda), com caixa
    semi-transparente atrás do texto pra garantir leitura sobre qualquer fundo."""
    estilo = (
        f"FontName={LEGENDA_FONTE},FontSize={LEGENDA_TAMANHO},"
        f"PrimaryColour={LEGENDA_COR_TEXTO},BackColour={LEGENDA_COR_FUNDO},"
        f"BorderStyle=3,Outline=0,Shadow=0,Alignment=2,"
        f"MarginV={LEGENDA_MARGEM_V},MarginL={LEGENDA_MARGEM_LR},MarginR={LEGENDA_MARGEM_LR}"
    )
    srt_escapado = _escapar_caminho_ffmpeg(caminho_srt)
    filtro = f"subtitles='{srt_escapado}':force_style='{estilo}'"

    r = subprocess.run(
        ["ffmpeg", "-y", "-i", caminho_video, "-vf", filtro,
         "-c:v", "libx264", "-c:a", "copy", caminho_saida],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg (queima de legenda) falhou: {r.stderr[-800:]}")


def adicionar_legendas(caminho_video: str, caminho_saida: str, openai_token: str,
                        prompt_contexto: str = "", manter_srt: bool = True) -> str:
    """
    Pipeline completo: transcreve o áudio do vídeo final (Whisper) e queima a
    legenda nele. Retorna `caminho_saida`. O .srt fica salvo ao lado do vídeo
    (mesmo nome, extensão .srt), a menos que `manter_srt=False`.
    """
    pasta = os.path.dirname(os.path.abspath(caminho_saida)) or "."
    nome_base = os.path.splitext(os.path.basename(caminho_video))[0]
    caminho_srt = os.path.join(pasta, f"{nome_base}.srt")

    print("   🎙️  Transcrevendo áudio (Whisper) para gerar legenda...")
    transcrever_srt(caminho_video, caminho_srt, openai_token, prompt_contexto)
    print(f"      ✅ Legenda gerada: {caminho_srt}")

    print("   🔥 Queimando legenda no vídeo...")
    queimar_legenda(caminho_video, caminho_srt, caminho_saida)
    print(f"      ✅ Vídeo com legenda: {caminho_saida}")

    if not manter_srt:
        try:
            os.remove(caminho_srt)
        except OSError:
            pass

    return caminho_saida
