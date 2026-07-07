"""
Composição local do avatar sobre os slides, com posição controlada por nós
(em vez de deixar o HeyGen centralizar o avatar automaticamente).

Por que isso existe:
  No fluxo antigo (`video_generator.gerar_video`), o slide era enviado ao HeyGen
  como "background" da cena, e era o PRÓPRIO HeyGen quem decidia onde desenhar o
  avatar dentro do frame — normalmente centralizado, ignorando o espaço vazio que
  o slide já reserva à direita (ver `slides_generator._gerar_slide_cena`, onde o
  conteúdo ocupa só os 58% da esquerda).

Fluxo novo, por cena:
  1. HeyGen gera SÓ o avatar falando (igual ao vídeo que o código já gera hoje),
     sobre fundo verde sólido (chroma key).
  2. Baixamos esse clipe.
  3. Criamos um vídeo estático a partir do slide (PNG), com a mesma duração do
     clipe do avatar.
  4. Removemos o verde do avatar (colorkey) e o sobrepomos no canto escolhido
     do vídeo do slide — por padrão, à direita.
  5. Concatenamos todas as cenas no vídeo final.

Requer ffmpeg e ffprobe no PATH.
"""

import os
import re
import shutil
import subprocess
import tempfile
import uuid

import requests

from src.video_generator.gerador_videos_direto import (
    HEYGEN_ASPECT_RATIO,
    HEYGEN_BASE_URL,
    HEYGEN_ENGINE,
    HEYGEN_EXPRESSIVENESS,
    HEYGEN_MOTION_PROMPT,
    HEYGEN_SPEED,
    aguardar_video,
)

# ─── CONFIGURAÇÃO DE POSICIONAMENTO DO AVATAR ─────────────────────────────────
AVATAR_POSICAO      = "direita"   # direita | direita-baixo | direita-cima | esquerda | esquerda-baixo | esquerda-cima | centro
AVATAR_LARGURA_REL  = 0.42        # largura do avatar em relação à largura final (0.42 = mesma faixa livre do slide)
AVATAR_MARGEM_PX    = 0           # distância entre o avatar e a borda do frame
CHROMA_COR_HEYGEN   = "#00FF00"   # cor de fundo pedida ao HeyGen (chroma key)
CHROMA_SIMILARIDADE = 0.12        # tolerância do colorkey (0.0–1.0)
CHROMA_BLEND        = 0.08        # suavização da borda do recorte (0.0–1.0)
APLICAR_DESPILL     = True        # remove reflexo verde residual na borda do avatar
SAIDA_LARGURA       = 1280
SAIDA_ALTURA        = 720
SAIDA_FPS           = 25
# ───────────────────────────────────────────────────────────────────────────────


def _checar_binarios():
    for nome in ("ffmpeg", "ffprobe"):
        if not shutil.which(nome):
            raise RuntimeError(f"'{nome}' não encontrado no PATH.")


def _hex_para_0x(cor_hex: str) -> str:
    return "0x" + cor_hex.lstrip("#")


def _posicao_overlay(posicao: str, margem: int) -> tuple[str, str]:
    """Expressões (x, y) do filtro overlay do ffmpeg para a posição pedida."""
    posicoes = {
        "direita":        (f"W-w-{margem}", "(H-h)/2"),
        "direita-baixo":  (f"W-w-{margem}", f"H-h-{margem}"),
        "direita-cima":   (f"W-w-{margem}", f"{margem}"),
        "esquerda":       (f"{margem}",     "(H-h)/2"),
        "esquerda-baixo": (f"{margem}",     f"H-h-{margem}"),
        "esquerda-cima":  (f"{margem}",     f"{margem}"),
        "centro":         ("(W-w)/2",       "(H-h)/2"),
    }
    if posicao not in posicoes:
        raise ValueError(f"Posição inválida: '{posicao}'. Use uma de: {list(posicoes)}")
    return posicoes[posicao]


def _ffprobe_duracao(caminho_video: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", caminho_video],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"ffprobe falhou em {caminho_video}: {r.stderr[:300]}")
    return float(r.stdout.strip())


def _baixar_video(video_url: str, caminho_saida: str):
    r = requests.get(video_url, timeout=120)
    r.raise_for_status()
    with open(caminho_saida, "wb") as f:
        f.write(r.content)


# =============================================================================
# ETAPA 1 — HEYGEN GERA SÓ O AVATAR FALANDO, SOBRE FUNDO VERDE (CHROMA KEY)
# =============================================================================

def gerar_avatar_chroma_key(
    fala:         str,
    titulo:       str,
    heygen_token: str,
    avatar_id:    str,
    voice_id:     str,
    cor_fundo:    str = CHROMA_COR_HEYGEN,
) -> str:
    """Pede ao HeyGen o vídeo do avatar falando sobre fundo verde sólido. Retorna o video_id."""
    headers = {
        "X-Api-Key":       heygen_token,
        "Content-Type":    "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    payload = {
        "type":           "avatar",
        "avatar_id":      avatar_id,
        "voice_id":       voice_id,
        "script":         fala,
        "title":          titulo,
        "aspect_ratio":   HEYGEN_ASPECT_RATIO,
        "voice_settings": {"speed": HEYGEN_SPEED},
        "motion_prompt":  HEYGEN_MOTION_PROMPT,
        "expressiveness": HEYGEN_EXPRESSIVENESS,
        "engine":         {"type": HEYGEN_ENGINE},
        "background":     {"type": "color", "value": cor_fundo},
    }

    resp = requests.post(f"{HEYGEN_BASE_URL}/v3/videos", headers=headers, json=payload, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"HeyGen /v3/videos falhou: HTTP {resp.status_code} — {resp.text[:300]}")

    video_id = resp.json().get("data", {}).get("video_id")
    if not video_id:
        raise RuntimeError(f"HeyGen não retornou video_id: {resp.text[:300]}")
    return video_id


# =============================================================================
# ETAPA 2 — SLIDE (PNG) → VÍDEO ESTÁTICO COM A DURAÇÃO DO CLIPE DO AVATAR
# =============================================================================

def _gerar_video_do_slide(caminho_slide: str, duracao: float, caminho_saida: str):
    r = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", caminho_slide,
            "-t", f"{duracao:.3f}",
            "-vf", f"scale={SAIDA_LARGURA}:{SAIDA_ALTURA}",
            "-r", str(SAIDA_FPS),
            "-pix_fmt", "yuv420p",
            caminho_saida,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg (slide→vídeo) falhou: {r.stderr[-500:]}")


# =============================================================================
# ETAPA 3 — COMPOSIÇÃO: AVATAR (CHROMA KEY) SOBRE O SLIDE, NO CANTO ESCOLHIDO
# =============================================================================

def _montar_filtro(largura_avatar: int, x_expr: str, y_expr: str,
                    cor_chroma_0x: str, com_despill: bool) -> str:
    cadeia_avatar = (
        f"[1:v]format=yuva420p,"
        f"colorkey={cor_chroma_0x}:{CHROMA_SIMILARIDADE}:{CHROMA_BLEND}"
    )
    if com_despill:
        cadeia_avatar += ",despill=type=green"
    cadeia_avatar += f",scale={largura_avatar}:-1[avatar]"

    return f"{cadeia_avatar};[0:v][avatar]overlay={x_expr}:{y_expr}:format=auto[outv]"


def compor_avatar_sobre_slide(
    caminho_avatar:      str,
    caminho_slide_video: str,
    caminho_saida:       str,
    posicao:             str = AVATAR_POSICAO,
    largura_rel:         float = AVATAR_LARGURA_REL,
    margem:              int = AVATAR_MARGEM_PX,
    cor_chroma:          str = CHROMA_COR_HEYGEN,
):
    """
    Remove o fundo verde do avatar e o sobrepõe no vídeo de fundo (slide),
    no canto definido por `posicao`. O áudio final vem do clipe do avatar.
    """
    largura_avatar = int(SAIDA_LARGURA * largura_rel)
    x_expr, y_expr = _posicao_overlay(posicao, margem)
    cor_chroma_0x = _hex_para_0x(cor_chroma)

    def _rodar(com_despill: bool):
        filtro = _montar_filtro(largura_avatar, x_expr, y_expr, cor_chroma_0x, com_despill)
        return subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", caminho_slide_video,
                "-i", caminho_avatar,
                "-filter_complex", filtro,
                "-map", "[outv]",
                "-map", "1:a",
                "-c:v", "libx264", "-c:a", "aac",
                "-shortest",
                caminho_saida,
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )

    r = _rodar(com_despill=APLICAR_DESPILL)
    if r.returncode != 0 and APLICAR_DESPILL and "despill" in r.stderr.lower():
        # Build de ffmpeg sem o filtro 'despill' — refaz sem ele.
        r = _rodar(com_despill=False)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg (composição) falhou: {r.stderr[-800:]}")


# =============================================================================
# ETAPA 4 — CONCATENA TODAS AS CENAS NO VÍDEO FINAL
# =============================================================================

def _concatenar(caminhos: list[str], caminho_saida: str, pasta_temp: str):
    lista = os.path.join(pasta_temp, "concat.txt")
    with open(lista, "w", encoding="utf-8") as f:
        for c in caminhos:
            f.write(f"file '{os.path.abspath(c).replace(chr(92), '/')}'\n")

    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", caminho_saida],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if r.returncode != 0:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista,
             "-c:v", "libx264", "-c:a", "aac", caminho_saida],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg (concat) falhou: {r.stderr[-800:]}")


# =============================================================================
# ORQUESTRAÇÃO
# =============================================================================

def gerar_video_avatar_no_canto(
    cenas:        list[dict],
    disciplina:   str,
    heygen_token: str,
    avatar_id:    str | None = None,
    voice_id:     str | None = None,
    posicao:      str = AVATAR_POSICAO,
    pasta_temp:   str | None = None,
) -> str:
    """
    cenas: [{"fala": str, "slide_path": str}, ...]
           slide_path = PNG já gerado (ex.: via slides_generator.gerar_slides)

    Para cada cena: gera o avatar no HeyGen (fundo verde) → baixa → cria vídeo
    do slide com a mesma duração → sobrepõe o avatar (sem fundo) no canto
    `posicao`. Concatena tudo e retorna o caminho do vídeo final.
    """
    _checar_binarios()

    avatar_id = avatar_id or os.getenv("HEYGEN_AVATAR_ID")
    voice_id  = voice_id  or os.getenv("HEYGEN_VOICE_ID")
    if not avatar_id:
        raise ValueError("HEYGEN_AVATAR_ID não configurado.")
    if not voice_id:
        raise ValueError("HEYGEN_VOICE_ID não configurado.")

    pasta_temp = pasta_temp or tempfile.mkdtemp(prefix="avatar_canto_")
    os.makedirs(pasta_temp, exist_ok=True)

    caminhos_cena_final = []
    total = len(cenas)

    for i, cena in enumerate(cenas, 1):
        fala = (cena.get("fala") or "").strip()
        slide_path = cena.get("slide_path")
        if not fala or not slide_path:
            print(f"   ⚠️ Cena {i}/{total} sem fala/slide — pulando")
            continue

        print(f"   🎬 Cena {i}/{total} — gerando avatar (chroma key) no HeyGen...")
        video_id = gerar_avatar_chroma_key(
            fala, f"{disciplina} — Cena {i}/{total}", heygen_token, avatar_id, voice_id,
        )
        info = aguardar_video(video_id, heygen_token, max_min=5.0)
        if not info.get("video_url"):
            raise RuntimeError(f"Sem video_url na cena {i}")

        caminho_avatar = os.path.join(pasta_temp, f"avatar_{i:03d}.mp4")
        _baixar_video(info["video_url"], caminho_avatar)
        print(f"      ✅ avatar baixado: {os.path.getsize(caminho_avatar) // 1024} KB")

        duracao = _ffprobe_duracao(caminho_avatar)
        caminho_slide_video = os.path.join(pasta_temp, f"slide_{i:03d}.mp4")
        _gerar_video_do_slide(slide_path, duracao, caminho_slide_video)

        caminho_final_cena = os.path.join(pasta_temp, f"cena_{i:03d}_final.mp4")
        compor_avatar_sobre_slide(
            caminho_avatar, caminho_slide_video, caminho_final_cena, posicao=posicao,
        )
        print(f"      ✅ cena composta ({posicao}): {caminho_final_cena}")

        caminhos_cena_final.append(caminho_final_cena)

    if not caminhos_cena_final:
        raise RuntimeError("Nenhuma cena gerada.")

    nome_saida = re.sub(r"[^\w-]+", "_", disciplina.strip(), flags=re.UNICODE).strip("_") or "video"
    caminho_saida = os.path.join(pasta_temp, f"{nome_saida}_final_canto.mp4")

    if len(caminhos_cena_final) == 1:
        shutil.copy(caminhos_cena_final[0], caminho_saida)
    else:
        print(f"   🔗 Concatenando {len(caminhos_cena_final)} cena(s)...")
        _concatenar(caminhos_cena_final, caminho_saida, pasta_temp)

    print(f"   ✅ Vídeo final: {caminho_saida}")
    return caminho_saida


# =============================================================================
# EXEMPLO DE USO — integra com o parser de roteiro e o gerador de slides já existentes
# =============================================================================

if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv

    from src.video_generator.slides_generator import gerar_slides
    from src.video_generator.video_generator import _parsear_roteiro_blocos

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Gera vídeo com avatar HeyGen posicionado no canto sobre slides."
    )
    parser.add_argument("roteiro_txt", help="Arquivo .txt com o roteiro (formato Bloco/[AVATAR]).")
    parser.add_argument("disciplina", help="Nome da disciplina (título das cenas).")
    parser.add_argument("--saida", default="video_final.mp4", help="Caminho do mp4 final.")
    parser.add_argument("--posicao", default=AVATAR_POSICAO,
                         choices=["direita", "direita-baixo", "direita-cima",
                                  "esquerda", "esquerda-baixo", "esquerda-cima", "centro"])
    args = parser.parse_args()

    heygen_token = os.getenv("HEYGEN_API_KEY")
    if not heygen_token:
        raise SystemExit("HEYGEN_API_KEY não configurada no .env.")

    with open(args.roteiro_txt, "r", encoding="utf-8") as f:
        roteiro = f.read()

    cenas_roteiro = _parsear_roteiro_blocos(roteiro)

    pasta_trabalho = tempfile.mkdtemp(prefix="pipeline_canto_")
    pasta_slides = os.path.join(pasta_trabalho, "slides")
    caminhos_slides = gerar_slides(cenas_roteiro, pasta_slides, args.disciplina)

    cenas_para_video = [
        {"fala": cena["fala"], "slide_path": slide}
        for cena, slide in zip(cenas_roteiro, caminhos_slides)
        if cena.get("fala", "").strip()
    ]

    caminho_temp = gerar_video_avatar_no_canto(
        cenas_para_video, args.disciplina, heygen_token, posicao=args.posicao,
        pasta_temp=pasta_trabalho,
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.saida)) or ".", exist_ok=True)
    shutil.move(caminho_temp, args.saida)
    print(f"🎉 Concluído: {args.saida}")
