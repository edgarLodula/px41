"""
Gera imagens ilustrativas para os slides a partir do `imagem_prompt`
retornado por `slides_content_generator.gerar_conteudo_slides`, usando a
API de imagens da OpenAI.

Cacheia em disco (pasta irmã de `pasta_slides`) para não regenerar a cada
execução — mesmo padrão de cache usado para `slides_content.json`.
"""
import base64
import io
import os

import numpy as np
import requests
from openai import OpenAI
from PIL import Image

IMAGEM_MODELO  = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
# Paisagem (1536x1024, ~1.5:1) em vez de quadrada — casa melhor com a caixa
# larga/baixa reservada pra imagem no slide (ver slides_generator.py), então
# ela aparece bem maior ali sem cortar nada (contida, não esticada).
IMAGEM_TAMANHO = os.getenv("OPENAI_IMAGE_SIZE", "1536x1024")

# O slide tem fundo azul escuro (ver slides_generator.BG_COLOR) — se a IA
# desenhar o conteúdo em tons escuros/apagados (marrom, oliva, sépia), a
# imagem quase some contra o fundo. LUMINANCIA_MINIMA é o piso aceitável
# (0-255, luminância média só dos pixels não-transparentes); abaixo disso a
# imagem é descartada e regenerada com um prompt mais insistente.
LUMINANCIA_MINIMA = 130
TENTATIVAS_POR_IMAGEM = 2

_PROMPT_BASE = (
    "{prompt}. Educational illustration, clean flat vector style, no text, "
    "no watermark, no borders. This will be displayed over a dark navy blue "
    "background, so it MUST use bright, vivid, highly saturated colors "
    "(vivid blues, reds, oranges, yellows, greens, white) with strong "
    "contrast — absolutely NO dark, muted, desaturated, sepia, brown, "
    "grayscale or monochrome tones anywhere in the image."
)
_PROMPT_REFORCO = (
    "{prompt}. Educational illustration, clean flat vector style, no text, "
    "no watermark, no borders. CRITICAL: the previous attempt came out too "
    "dark/muted to be usable. Redo it using ONLY bright, saturated, "
    "high-contrast colors (think vivid poster/infographic palette: bright "
    "blue, red, orange, yellow, white) — the artwork will sit on a dark "
    "navy blue background, so anything dark, dull, brownish, sepia or "
    "grayscale is unacceptable and unreadable."
)


def _print_seguro(texto: str) -> None:
    """print() que nunca lança — em console Windows sem UTF-8 (cp1252),
    imprimir emoji derruba UnicodeEncodeError; aqui cai pra uma versão
    sem os caracteres problemáticos em vez de propagar o erro."""
    try:
        print(texto)
    except UnicodeEncodeError:
        print(texto.encode("ascii", errors="replace").decode("ascii"))


def _luminancia_media_opaca(conteudo_bin: bytes) -> float | None:
    """Luminância média (0-255) dos pixels não-transparentes da imagem.
    None se a imagem for quase toda transparente (nada de conteúdo pra
    medir) — nesse caso não há como avaliar, então deixamos passar."""
    im = Image.open(io.BytesIO(conteudo_bin)).convert("RGBA")
    arr = np.asarray(im, dtype=np.float32)
    opacos = arr[..., 3] >= 128
    if not opacos.any():
        return None
    rgb = arr[..., :3][opacos]
    luminancia = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return float(luminancia.mean())


def _clarear_imagem(conteudo_bin: bytes, luminancia_atual: float, alvo: float = LUMINANCIA_MINIMA) -> bytes:
    """Clareia os canais RGB (preservando o alfa) até a luminância média
    opaca alcançar `alvo`. Usado como último recurso quando nenhuma
    tentativa de geração saiu clara o bastante — garante que o slide
    sempre tenha imagem, em vez de descartá-la e ficar só com texto."""
    im = Image.open(io.BytesIO(conteudo_bin)).convert("RGBA")
    arr = np.asarray(im, dtype=np.float32)
    fator = min(3.0, (alvo / max(luminancia_atual, 1.0)) * 1.08)
    arr[..., :3] = np.clip(arr[..., :3] * fator, 0, 255)
    im_clara = Image.fromarray(arr.astype(np.uint8), mode="RGBA")
    buf = io.BytesIO()
    im_clara.save(buf, format="PNG")
    return buf.getvalue()


def _gerar_uma_imagem(client: OpenAI, prompt_texto: str) -> bytes:
    kwargs = dict(model=IMAGEM_MODELO, prompt=prompt_texto, size=IMAGEM_TAMANHO, n=1)
    if IMAGEM_MODELO == "gpt-image-1":
        # Transparência de verdade via parâmetro nativo da API — pedir
        # "fundo transparente" só no texto do prompt fazia o modelo
        # "desenhar" a transparência como um cinza/preto sólido feio em
        # vez de gerar um canal alfa de verdade.
        kwargs["background"] = "transparent"
    resp = client.images.generate(**kwargs)
    dado = resp.data[0]
    if getattr(dado, "b64_json", None):
        return base64.b64decode(dado.b64_json)
    if getattr(dado, "url", None):
        r = requests.get(dado.url, timeout=60)
        r.raise_for_status()
        return r.content
    raise RuntimeError("Resposta da API de imagens sem b64_json nem url.")


def gerar_imagens_slides(
    conteudos:    list[dict],
    pasta_slides: str,
    openai_token: str | None,
) -> list[str | None]:
    """
    Gera 1 imagem PNG por conteúdo de slide que tiver `imagem_prompt`
    preenchido. Retorna list[str | None] do mesmo tamanho de `conteudos`,
    com o caminho absoluto da imagem gerada (ou None apenas quando o slide
    não precisa de imagem, ou a chamada à API falhou de verdade — ex: erro
    de rede). Uma imagem que saiu escura demais em todas as tentativas NÃO
    é descartada: é clareada programaticamente e usada mesmo assim, então
    o slide sempre tem imagem.
    """
    if not openai_token:
        return [None] * len(conteudos)

    pasta_pai     = os.path.dirname(pasta_slides.rstrip("/\\"))
    pasta_imagens = os.path.join(pasta_pai, "slides_imagens")
    os.makedirs(pasta_imagens, exist_ok=True)

    client   = OpenAI(api_key=openai_token)
    caminhos: list[str | None] = []

    for i, conteudo in enumerate(conteudos):
        prompt = (conteudo or {}).get("imagem_prompt")
        if not prompt or not str(prompt).strip():
            caminhos.append(None)
            continue

        caminho = os.path.join(pasta_imagens, f"img_{i:03d}.png")
        if os.path.isfile(caminho):
            caminhos.append(caminho)
            continue

        conteudo_bin  = None
        melhor_bin    = None
        melhor_lum    = -1.0
        try:
            for tentativa in range(1, TENTATIVAS_POR_IMAGEM + 1):
                modelo_prompt = _PROMPT_REFORCO if tentativa > 1 else _PROMPT_BASE
                candidato = _gerar_uma_imagem(client, modelo_prompt.format(prompt=prompt))
                luminancia = _luminancia_media_opaca(candidato)
                if luminancia is None or luminancia >= LUMINANCIA_MINIMA:
                    conteudo_bin = candidato
                    break
                if luminancia > melhor_lum:
                    melhor_bin, melhor_lum = candidato, luminancia
                _print_seguro(
                    f"   [AVISO] Imagem do slide {i + 1} saiu escura demais "
                    f"(luminância {luminancia:.0f}/255, mínimo {LUMINANCIA_MINIMA}) "
                    f"— tentativa {tentativa}/{TENTATIVAS_POR_IMAGEM}."
                )

            if conteudo_bin is None:
                # Nenhuma tentativa passou do limiar — em vez de descartar a
                # imagem (slide ficaria só com texto), clareamos a melhor
                # candidata programaticamente. A imagem sempre aparece.
                conteudo_bin = _clarear_imagem(melhor_bin, melhor_lum)
                _print_seguro(
                    f"   [AVISO] Imagem do slide {i + 1} continuou escura após "
                    f"{TENTATIVAS_POR_IMAGEM} tentativa(s) (melhor: {melhor_lum:.0f}/255) "
                    "— clareada automaticamente para uso."
                )

            with open(caminho, "wb") as f:
                f.write(conteudo_bin)
        except Exception as e:
            # NÃO envolve print() aqui: em consoles Windows sem UTF-8, um
            # print() com emoji pode lançar UnicodeEncodeError e cair neste
            # except mesmo com a imagem já salva com sucesso — duplicando o
            # append e desalinhando `caminhos` em relação a `conteudos`.
            caminhos.append(None)
            _print_seguro(f"   [AVISO] Falha ao gerar imagem do slide {i + 1}: {e}")
            continue

        caminhos.append(caminho)
        _print_seguro(f"   🖼️  Imagem do slide {i + 1} gerada: {caminho}")

    return caminhos
