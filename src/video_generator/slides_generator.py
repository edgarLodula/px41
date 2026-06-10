import os
from PIL import Image, ImageDraw, ImageFont

FONTE_PATH  = "C:/Windows/Fonts/arial.ttf"
BG_COLOR    = (26, 39, 68)        # #1a2744  — igual ao fundo HeyGen
TEXT_COLOR  = (255, 255, 255)
ACCENT_COLOR = (100, 150, 255)    # azul claro


def _carregar_fonte(tamanho):
    try:
        return ImageFont.truetype(FONTE_PATH, tamanho)
    except OSError:
        return ImageFont.load_default()


def _quebrar_linhas(draw, texto, fonte, largura_max):
    palavras = texto.split()
    linhas, linha = [], ""
    for palavra in palavras:
        teste = (linha + " " + palavra).strip()
        bbox = draw.textbbox((0, 0), teste, font=fonte)
        if bbox[2] <= largura_max:
            linha = teste
        else:
            if linha:
                linhas.append(linha)
            linha = palavra
    if linha:
        linhas.append(linha)
    return linhas


def _gerar_slide_cena(cena, caminho_saida, disciplina):
    """Gera 1 slide PNG para uma cena. Conteudo na metade esquerda — direita livre para avatar."""
    largura, altura = 1280, 720
    area_w = int(largura * 0.58)   # 58 % da largura para o conteúdo

    img  = Image.new("RGB", (largura, altura), BG_COLOR)
    draw = ImageDraw.Draw(img)

    fonte_titulo   = _carregar_fonte(32)
    fonte_destaque = _carregar_fonte(40)
    fonte_visual   = _carregar_fonte(24)

    # Faixa decorativa vertical
    draw.rectangle([(38, 0), (44, altura)], fill=ACCENT_COLOR)

    # Título da disciplina
    draw.text((60, 28), disciplina.upper(), font=fonte_titulo, fill=ACCENT_COLOR)

    # Separador horizontal
    draw.line([(60, 78), (area_w - 20, 78)], fill=ACCENT_COLOR, width=2)

    y = 108

    # Texto na tela (destaque principal)
    texto_tela = (cena.get("texto") or "").strip().strip("()")
    if texto_tela:
        linhas = _quebrar_linhas(draw, texto_tela, fonte_destaque, area_w - 80)
        for linha in linhas:
            draw.text((60, y), linha, font=fonte_destaque, fill=TEXT_COLOR)
            y += 54
        y += 16

    # Descrição visual — menor, no máximo 4 linhas
    visual = (cena.get("visual") or "").strip().strip("()")
    if visual:
        linhas_v = _quebrar_linhas(draw, visual, fonte_visual, area_w - 80)
        for linha in linhas_v[:4]:
            draw.text((60, y), linha, font=fonte_visual, fill=(180, 200, 255))
            y += 34

    img.save(caminho_saida)


def gerar_slides(cenas, pasta_saida, disciplina):
    """
    Gera 1 slide PNG por cena (já parseada).

    Parâmetros:
        cenas       — list[dict] com chaves fala, visual, texto
        pasta_saida — diretório de saída
        disciplina  — título exibido em todos os slides

    Retorna list[str] com caminhos absolutos, na mesma ordem de cenas.
    """
    os.makedirs(pasta_saida, exist_ok=True)
    caminhos = []
    for i, cena in enumerate(cenas):
        caminho = os.path.join(pasta_saida, f"slide_{i:03d}.png")
        _gerar_slide_cena(cena, caminho, disciplina)
        caminhos.append(os.path.abspath(caminho))
    print(f"   {len(caminhos)} slide(s) gerado(s) em: {pasta_saida}")
    return caminhos
