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
  3. Converte o .srt pra .ass, com PlayResX/PlayResY IGUAIS à resolução real
     do vídeo — sem isso, o `subtitles` do ffmpeg assume uma resolução de
     script diferente (384x288) e escala margens/fonte de forma
     imprevisível, o que quebra o texto palavra a palavra quando a legenda
     não é centralizada (margens assimétricas, ex.: pra evitar o avatar).
  4. Queima o .ass no vídeo com o filtro `ass` do ffmpeg (libass).

Requer ffmpeg no PATH (compilado com libass, o padrão do build "full" do
gyan.dev/BtbN já inclui).
"""

import os
import re
import subprocess

from openai import OpenAI

# ─── ESTILO DA LEGENDA (combina com a identidade visual "lousa" dos slides) ───
LEGENDA_FONTE       = "Arial"
LEGENDA_TAMANHO     = 30
LEGENDA_COR_TEXTO   = "&H00E8E8E8"   # branco giz (BGR invertido, ASS)
LEGENDA_COR_FUNDO   = "&H80000000"   # preto ~50% opaco (caixa atrás do texto)
LEGENDA_MARGEM_V    = 100            # distância da borda inferior (px) — livre do rodapé do slide
LEGENDA_MARGEM_LR   = 65             # margem lateral (px) — livre da barra amarela decorativa do slide (x≈38-46)
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


def _parsear_srt(caminho_srt: str) -> list[tuple[str, str, str]]:
    """Retorna [(inicio_ass, fim_ass, texto), ...] a partir de um .srt."""
    with open(caminho_srt, "r", encoding="utf-8") as f:
        conteudo = f.read()

    entradas = []
    for bloco in re.split(r"\n\s*\n", conteudo.strip()):
        linhas = bloco.strip().splitlines()
        if len(linhas) < 2:
            continue
        idx_tempo = 1 if "-->" in linhas[1] else 0
        m = re.search(r"(\d\d:\d\d:\d\d,\d\d\d)\s*-->\s*(\d\d:\d\d:\d\d,\d\d\d)", linhas[idx_tempo])
        if not m:
            continue
        texto = "\n".join(linhas[idx_tempo + 1:]).strip()
        if not texto:
            continue
        entradas.append((_srt_tempo_para_ass(m.group(1)), _srt_tempo_para_ass(m.group(2)), texto))
    return entradas


def _srt_tempo_para_ass(tempo_srt: str) -> str:
    """'01:02:03,340' -> '1:02:03.34' (ASS usa H:MM:SS.cc, centésimos)."""
    hms, ms = tempo_srt.split(",")
    h, m, s = hms.split(":")
    cs = int(ms) // 10
    return f"{int(h)}:{m}:{s}.{cs:02d}"


def _gerar_ass(caminho_srt: str, caminho_ass: str, largura: int, altura: int,
                alinhamento: int, margem_l: int, margem_r: int, margem_v: int):
    """
    Converte o .srt num .ass autoral, com PlayResX/PlayResY = resolução real
    do vídeo — assim FontSize/margens do estilo correspondem 1:1 a pixels,
    sem depender de heurísticas de escala do ffmpeg/libass.
    """
    cabecalho = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {largura}\n"
        f"PlayResY: {altura}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{LEGENDA_FONTE},{LEGENDA_TAMANHO},{LEGENDA_COR_TEXTO},{LEGENDA_COR_TEXTO},"
        f"&H00000000,{LEGENDA_COR_FUNDO},0,0,0,0,100,100,0,0,3,0,0,"
        f"{alinhamento},{margem_l},{margem_r},{margem_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    linhas_evento = []
    for inicio, fim, texto in _parsear_srt(caminho_srt):
        texto_ass = texto.replace("\n", "\\N")
        linhas_evento.append(f"Dialogue: 0,{inicio},{fim},Default,,0,0,0,,{texto_ass}\n")

    with open(caminho_ass, "w", encoding="utf-8") as f:
        f.write(cabecalho)
        f.writelines(linhas_evento)


def queimar_legenda(caminho_video: str, caminho_srt: str, caminho_saida: str,
                     evitar_lado: str | None = None, reservar_px: int = 0,
                     largura_video: int = 1280, altura_video: int = 720):
    """Queima a legenda no vídeo, no rodapé, com caixa semi-transparente atrás
    do texto pra garantir leitura sobre qualquer fundo.

    Se `evitar_lado` for "direita" ou "esquerda", a legenda fica alinhada ao
    lado OPOSTO e reserva `reservar_px` de largura no lado do avatar, pra não
    ficar sobreposta a ele. Se `evitar_lado` for None, fica centralizada
    ocupando a largura toda (comportamento padrão).
    """
    margem_lr = LEGENDA_MARGEM_LR
    if evitar_lado == "direita":
        alinhamento, margem_l, margem_r = 1, margem_lr, reservar_px
    elif evitar_lado == "esquerda":
        alinhamento, margem_l, margem_r = 3, reservar_px, margem_lr
    else:
        alinhamento, margem_l, margem_r = 2, margem_lr, margem_lr

    caminho_ass = os.path.splitext(caminho_srt)[0] + ".ass"
    _gerar_ass(caminho_srt, caminho_ass, largura_video, altura_video,
               alinhamento, margem_l, margem_r, margem_v=LEGENDA_MARGEM_V)

    ass_escapado = _escapar_caminho_ffmpeg(caminho_ass)
    filtro = f"ass='{ass_escapado}'"

    r = subprocess.run(
        ["ffmpeg", "-y", "-i", caminho_video, "-vf", filtro,
         "-c:v", "libx264", "-c:a", "copy", caminho_saida],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg (queima de legenda) falhou: {r.stderr[-800:]}")


def adicionar_legendas(caminho_video: str, caminho_saida: str, openai_token: str,
                        prompt_contexto: str = "", manter_srt: bool = True,
                        evitar_lado: str | None = None, reservar_px: int = 0,
                        largura_video: int = 1280, altura_video: int = 720) -> str:
    """
    Pipeline completo: transcreve o áudio do vídeo final (Whisper) e queima a
    legenda nele. Retorna `caminho_saida`. O .srt fica salvo ao lado do vídeo
    (mesmo nome, extensão .srt), a menos que `manter_srt=False`.

    `evitar_lado`/`reservar_px`: ver `queimar_legenda` — usados pra legenda
    não ficar sobreposta ao avatar quando ele estiver no rodapé.
    """
    pasta = os.path.dirname(os.path.abspath(caminho_saida)) or "."
    nome_base = os.path.splitext(os.path.basename(caminho_video))[0]
    caminho_srt = os.path.join(pasta, f"{nome_base}.srt")

    print("   🎙️  Transcrevendo áudio (Whisper) para gerar legenda...")
    transcrever_srt(caminho_video, caminho_srt, openai_token, prompt_contexto)
    print(f"      ✅ Legenda gerada: {caminho_srt}")

    print("   🔥 Queimando legenda no vídeo...")
    queimar_legenda(caminho_video, caminho_srt, caminho_saida, evitar_lado, reservar_px,
                     largura_video, altura_video)
    print(f"      ✅ Vídeo com legenda: {caminho_saida}")

    if not manter_srt:
        try:
            os.remove(caminho_srt)
        except OSError:
            pass

    return caminho_saida
