import os
from PIL import Image, ImageDraw, ImageFont


FONTE_PATH = "C:/Windows/Fonts/arial.ttf"


def carregar_fonte(tamanho):
    return ImageFont.truetype(FONTE_PATH, tamanho)


def dividir_em_blocos(texto, max_palavras=120):
    palavras = texto.split()
    blocos = []

    for i in range(0, len(palavras), max_palavras):
        bloco = " ".join(palavras[i:i+max_palavras])
        blocos.append(bloco)

    return blocos


def gerar_slide_simples(texto, caminho_saida, disciplina):
    largura, altura = 1280, 720

    img = Image.new("RGB", (largura, altura), "white")
    draw = ImageDraw.Draw(img)

    fonte_titulo = carregar_fonte(40)
    fonte_texto = carregar_fonte(28)

    # título
    draw.text((50, 40), disciplina, font=fonte_titulo, fill="black")

    # quebra de linha manual
    linhas = []
    palavras = texto.split()
    linha = ""

    for palavra in palavras:
        if len(linha + palavra) < 60:
            linha += palavra + " "
        else:
            linhas.append(linha)
            linha = palavra + " "

    linhas.append(linha)

    y = 150
    for linha in linhas:
        draw.text((50, y), linha, font=fonte_texto, fill="black")
        y += 40

    img.save(caminho_saida)


def gerar_slides(roteiro, pasta_saida, disciplina):
    blocos = dividir_em_blocos(roteiro)

    for i, bloco in enumerate(blocos):
        caminho_slide = os.path.join(pasta_saida, f"slide_{i:03d}.png")
        gerar_slide_simples(bloco, caminho_slide, disciplina)

    print(f"   🖼️ {len(blocos)} slides gerados")