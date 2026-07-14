import json
import os
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTE_PATH       = "assets/fonts/Roboto-Regular.ttf"     # fonte bundled
FONTE_BOLD_PATH  = "assets/fonts/Fredericka-the-Great.ttf" # título estilo giz
BG_COLOR         = (26, 42, 26)       # verde lousa escuro
TEXT_COLOR       = (232, 232, 208)    # branco giz (levemente amarelado)
ACCENT_COLOR     = (255, 235, 59)     # amarelo giz
SUBTITLE_COLOR   = (180, 180, 155)    # giz apagado
MARCADOR         = "•"    # "▸" não existe na maioria das fontes de fallback (ex.: Calibri) e aparecia como tofu (☐)

# Avatar sobreposto (PiP) no canto inferior do vídeo final (ver
# compor_avatar_slides.AVATAR_POSICAO/AVATAR_LARGURA_REL). Reservamos essa
# faixa para o texto do slide nunca ficar escondido atrás do avatar.
MARGEM_INFERIOR_AVATAR = 320
AVATAR_LADO            = "direita"  # "esquerda" | "direita" — deve casar com o lado usado em AVATAR_POSICAO

TIPO_LISTA        = "lista"
TIPO_ABERTURA     = "abertura"
TIPO_ENCERRAMENTO = "encerramento"
TIPO_DEFINICAO    = "definicao"
TIPO_PROCESSO     = "processo"
TIPO_NUMERO       = "numero"

_DISC_ABREV = {
    "anatomia": "AN", "fisiologia": "FS", "enfermagem": "EN",
    "português": "PT", "portugues": "PT",
    "matemática": "MT", "matematica": "MT",
    "física": "FC", "fisica": "FC",
    "química": "QM", "quimica": "QM",
    "biologia": "BI", "história": "HI", "historia": "HI",
    "geografia": "GE", "informática": "TI", "informatica": "TI",
}


# ── Helpers de fonte / texto ───────────────────────────────────────────────────

def _carregar_fonte(tamanho, negrito=False):
    caminho = FONTE_BOLD_PATH if negrito else FONTE_PATH
    try:
        return ImageFont.truetype(caminho, tamanho)
    except OSError:
        try:
            return ImageFont.truetype(FONTE_PATH, tamanho)
        except OSError:
            pass
    # Fallback: fontes do sistema Windows
    _win_bold   = r"C:\Windows\Fonts\calibrib.ttf"
    _win_normal = r"C:\Windows\Fonts\calibri.ttf"
    try:
        return ImageFont.truetype(_win_bold if negrito else _win_normal, tamanho)
    except OSError:
        try:
            return ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", tamanho)
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


def _alt(draw, fonte):
    bbox = draw.textbbox((0, 0), "Ag", font=fonte)
    return bbox[3] - bbox[1]


def _encurtar(texto, max_palavras):
    p = texto.split()
    if len(p) <= max_palavras:
        return texto.rstrip(".;,:")
    return " ".join(p[:max_palavras]).rstrip(".;,:") + "..."


def _abrev_disc(disciplina):
    d = disciplina.lower()
    for key, ab in _DISC_ABREV.items():
        if key in d:
            return ab
    partes = disciplina.split()
    return (partes[0][:2]).upper() if partes else "XX"


# ── Extração de conteúdo ───────────────────────────────────────────────────────

def _extrair_conteudo(cena, conteudo, disciplina):
    titulo, topicos, destaque = "", [], None
    if isinstance(conteudo, dict):
        titulo   = (conteudo.get("titulo") or "").strip()
        topicos  = list(conteudo.get("topicos") or [])
        d = conteudo.get("destaque") or ""
        destaque = d.strip() if isinstance(d, str) and d.strip() else None

    if not titulo:
        texto_tela = (cena.get("texto") or "").strip().strip("()")
        if texto_tela:
            titulo = texto_tela.split("\n")[0].split(".")[0][:60].strip()
        if not titulo:
            titulo = " ".join((cena.get("fala") or "").split()[:6]) or disciplina

    topicos = [str(t).strip() for t in topicos if str(t).strip()]
    if len(topicos) < 3:
        cand = []
        visual = (cena.get("visual") or "").strip().strip("()")
        if visual:
            for sep in [";", "\n", ". ", " — ", " - "]:
                pedacos = [x.strip(" -•▸") for x in visual.split(sep) if x.strip()]
                if len(pedacos) >= 2:
                    cand.extend(pedacos); break
        if len(cand) < 3:
            fala = (cena.get("fala") or "").replace("!", ".").replace("?", ".")
            cand.extend([s.strip() for s in fala.split(".") if s.strip() and len(s.strip()) > 10])
        for c in cand:
            c = _encurtar(c, 12)
            if c and c not in topicos:
                topicos.append(c)

    topicos = topicos[:5] or ["Próxima etapa do conteúdo"]
    return titulo, topicos, destaque


# ── Detecção de tipo de cena ───────────────────────────────────────────────────

def _detectar_tipo(cena, conteudo, indice, total):
    if indice == 0:
        return TIPO_ABERTURA
    if indice == total - 1:
        return TIPO_ENCERRAMENTO

    # Tipo declarado pelo gerador de conteúdo (campo opcional)
    if conteudo and isinstance(conteudo.get("tipo"), str):
        t = conteudo["tipo"].lower().strip()
        if t in (TIPO_LISTA, TIPO_DEFINICAO, TIPO_PROCESSO, TIPO_NUMERO):
            return t

    topicos = list((conteudo.get("topicos") if conteudo else None) or [])
    fala    = (cena.get("fala") or "").lower()
    titulo  = ((conteudo.get("titulo") if conteudo else "") or "").lower()
    tudo    = titulo + " " + fala + " " + " ".join(str(t) for t in topicos)

    if re.search(r'\b\d{2,}[\.,]?\d*\s*%', tudo):
        return TIPO_NUMERO
    if any(re.match(r'^\s*\d+[.)]\s', str(t)) for t in topicos):
        return TIPO_PROCESSO
    return TIPO_LISTA


# ── Primitivos de desenho ──────────────────────────────────────────────────────

def _barra_lateral(draw, altura):
    draw.rectangle([(38, 0), (46, altura)], fill=ACCENT_COLOR)


def _desenhar_tag(draw, destaque, x_max, y_top):
    if not destaque:
        return
    fonte_tag = _carregar_fonte(20, negrito=True)
    tag_text  = destaque.upper()[:22]
    bbox      = draw.textbbox((0, 0), tag_text, font=fonte_tag)
    pad_x, pad_y = 14, 7
    tag_w = (bbox[2] - bbox[0]) + 2 * pad_x
    tag_h = (bbox[3] - bbox[1]) + 2 * pad_y
    tag_x = x_max - tag_w
    draw.rectangle([(tag_x, y_top), (tag_x + tag_w, y_top + tag_h)], fill=ACCENT_COLOR)
    draw.text((tag_x + pad_x, y_top + pad_y - 4), tag_text, font=fonte_tag, fill=BG_COLOR)


def _icone_disc(draw, disciplina, cx, cy, raio=22):
    draw.ellipse([(cx - raio, cy - raio), (cx + raio, cy + raio)], fill=ACCENT_COLOR)
    fonte = _carregar_fonte(16, negrito=True)
    abrev = _abrev_disc(disciplina)
    bbox  = draw.textbbox((0, 0), abrev, font=fonte)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 1), abrev, font=fonte, fill=BG_COLOR)


def _texto_escola(draw, x0, x_max, altura, fonte_escola):
    """Assinatura 'Escola Técnica San Marino', do lado oposto ao avatar (ver AVATAR_LADO)."""
    texto = "Escola Técnica San Marino"
    y = altura - 58
    if AVATAR_LADO == "direita":
        draw.text((x0, y), texto, font=fonte_escola, fill=ACCENT_COLOR)
    else:
        bbox = draw.textbbox((0, 0), texto, font=fonte_escola)
        draw.text((x_max - (bbox[2] - bbox[0]), y), texto, font=fonte_escola, fill=ACCENT_COLOR)


def _rodape(draw, disciplina, numero, total, x0, x_max, altura):
    """Rodapé fica do lado oposto ao avatar (ver AVATAR_LADO), pra não ficar escondido atrás dele."""
    fonte = _carregar_fonte(18)
    y = altura - 36
    texto = f"{disciplina}   •   {numero} / {total}"
    if AVATAR_LADO == "direita":
        draw.text((x0, y), texto, font=fonte, fill=SUBTITLE_COLOR)
    else:
        bbox = draw.textbbox((0, 0), texto, font=fonte)
        draw.text((x_max - (bbox[2] - bbox[0]), y), texto, font=fonte, fill=SUBTITLE_COLOR)


def _titulo_linha(draw, titulo, x0, x_max, y_start, fonte_titulo):
    titulo = _encurtar(titulo, 10)
    """Título em caps + separador. Retorna y logo após a linha."""
    lmax   = x_max - x0
    linhas = _quebrar_linhas(draw, titulo.upper(), fonte_titulo, lmax)[:2]
    y      = y_start
    h      = _alt(draw, fonte_titulo)
    for linha in linhas:
        draw.text((x0, y), linha, font=fonte_titulo, fill=ACCENT_COLOR)
        y += h + 10
    y += 4
    draw.line([(x0, y), (x_max - 20, y)], fill=ACCENT_COLOR, width=3)
    return y + 24


def _linha_com_destaque(draw, x, y, linha, destaque, fonte_normal, fonte_bold):
    if not destaque:
        draw.text((x, y), linha, font=fonte_normal, fill=TEXT_COLOR)
        return
    dest_palavras = [p.strip(".,;:!?") for p in destaque.lower().split()]
    palavras = linha.split()
    xc = x
    i = 0
    while i < len(palavras):
        janela = [p.lower().strip(".,;:!?") for p in palavras[i:i+len(dest_palavras)]]
        casou = janela == dest_palavras
        n = len(dest_palavras) if casou else 1
        token = " ".join(palavras[i:i+n]) + ("" if i+n == len(palavras) else " ")
        fonte = fonte_bold if casou else fonte_normal
        cor = ACCENT_COLOR if casou else TEXT_COLOR
        draw.text((xc, y - (1 if casou else 0)), token, font=fonte, fill=cor)
        bbox = draw.textbbox((0, 0), token, font=fonte)
        xc += bbox[2] - bbox[0]
        i += n


def _bullets(draw, topicos, destaque, x0, x_max, y_ini, altura_disp,
             fonte_topico, fonte_bold_topico, fonte_marcador):
    tamanho = fonte_topico.size
    while tamanho > 18:
        fonte_topico = _carregar_fonte(tamanho)
        fonte_bold_topico = _carregar_fonte(tamanho, negrito=True)
        marc_w = draw.textbbox((0,0), MARCADOR+" ", font=fonte_marcador)[2]
        lbullet = (x_max - x0) - marc_w
        alt_linha = _alt(draw, fonte_topico) + 8
        blocos = [_quebrar_linhas(draw, t, fonte_topico, lbullet)[:2] for t in topicos]
        altura_txt = sum(len(b) * alt_linha for b in blocos)
        if altura_txt <= altura_disp:
            break
        tamanho -= 2
    marc_w     = draw.textbbox((0, 0), MARCADOR + " ", font=fonte_marcador)[2]
    lbullet    = (x_max - x0) - marc_w
    alt_linha  = _alt(draw, fonte_topico) + 8
    blocos     = [_quebrar_linhas(draw, t, fonte_topico, lbullet)[:2] for t in topicos]
    altura_txt = sum(len(b) * alt_linha for b in blocos)
    sobra      = altura_disp - altura_txt
    espaco     = max(20, sobra // (len(blocos) + 1)) if sobra > 0 else 20

    y = y_ini + max(0, espaco // 2)
    for linhas, topico in zip(blocos, topicos):
        if not linhas:
            continue
        if y + len(linhas) * alt_linha > y_ini + altura_disp - 10:
            print("   [AVISO] Tópico omitido (sem espaço vertical).")
            break
        draw.text((x0, y - 4), MARCADOR, font=fonte_marcador, fill=ACCENT_COLOR)
        for linha in linhas:
            _linha_com_destaque(draw, x0 + marc_w, y, linha, destaque,
                                fonte_topico, fonte_bold_topico)
            y += alt_linha
        y += espaco


# ── Layouts por tipo ───────────────────────────────────────────────────────────

def _layout_lista(img, draw, titulo, topicos, destaque, disciplina, numero, total, dims):
    largura, altura, x0, x_max = dims
    _barra_lateral(draw, altura)
    _desenhar_tag(draw, destaque, x_max, 28)
    y = _titulo_linha(draw, titulo, x0, x_max, 56, _carregar_fonte(44, negrito=True))
    _bullets(
        draw, topicos, destaque, x0, x_max, y, altura - MARGEM_INFERIOR_AVATAR - y,
        _carregar_fonte(30), _carregar_fonte(30, negrito=True), _carregar_fonte(32, negrito=True),
    )
    _rodape(draw, disciplina, numero, total, x0, x_max, altura)


def _layout_abertura(img, draw, titulo, topicos, destaque, disciplina, numero, total, dims):
    largura, altura, x0, x_max = dims
    _barra_lateral(draw, altura)

    # Ícone da disciplina — canto sup. dir.
    _icone_disc(draw, disciplina, x_max - 28, 44)

    fonte_disc   = _carregar_fonte(52, negrito=True)
    fonte_sub    = _carregar_fonte(26)
    fonte_escola = _carregar_fonte(20, negrito=True)
    fonte_marc   = _carregar_fonte(24, negrito=True)
    fonte_bullet = _carregar_fonte(22)

    # Nome da disciplina (recua da direita para não tocar no ícone)
    lmax = x_max - x0 - 60
    y    = 72
    for linha in _quebrar_linhas(draw, disciplina.upper(), fonte_disc, lmax)[:2]:
        draw.text((x0, y), linha, font=fonte_disc, fill=ACCENT_COLOR)
        y += _alt(draw, fonte_disc) + 10
    y += 4
    draw.line([(x0, y), (x_max - 20, y)], fill=ACCENT_COLOR, width=3)
    y += 24

    # Subtítulo
    subtitulo = titulo or (topicos[0] if topicos else "")
    for linha in _quebrar_linhas(draw, subtitulo, fonte_sub, x_max - x0)[:2]:
        draw.text((x0, y), linha, font=fonte_sub, fill=TEXT_COLOR)
        y += 34
    y += 12

    # Bullets adicionais
    marc_w = draw.textbbox((0, 0), MARCADOR + " ", font=fonte_marc)[2]
    for t in topicos[1:4]:
        for linha in _quebrar_linhas(draw, t, fonte_bullet, x_max - x0 - marc_w)[:1]:
            draw.text((x0, y - 2), MARCADOR, font=fonte_marc, fill=ACCENT_COLOR)
            draw.text((x0 + marc_w, y), linha, font=fonte_bullet, fill=SUBTITLE_COLOR)
            y += 30

    _texto_escola(draw, x0, x_max, altura, fonte_escola)
    _rodape(draw, disciplina, numero, total, x0, x_max, altura)


def _layout_encerramento(img, draw, titulo, topicos, destaque, disciplina, numero, total, dims):
    largura, altura, x0, x_max = dims
    _barra_lateral(draw, altura)

    fonte_cta    = _carregar_fonte(42, negrito=True)
    fonte_passo  = _carregar_fonte(26)
    fonte_escola = _carregar_fonte(20, negrito=True)
    fonte_marc   = _carregar_fonte(28, negrito=True)

    y      = _titulo_linha(draw, titulo or "Próximos Passos", x0, x_max, 56, fonte_cta)
    marc_w = draw.textbbox((0, 0), MARCADOR + " ", font=fonte_marc)[2]
    for t in topicos[:4]:
        for linha in _quebrar_linhas(draw, t, fonte_passo, x_max - x0 - marc_w)[:2]:
            draw.text((x0, y - 2), MARCADOR, font=fonte_marc, fill=ACCENT_COLOR)
            draw.text((x0 + marc_w, y), linha, font=fonte_passo, fill=TEXT_COLOR)
            y += 34
        y += 8

    _texto_escola(draw, x0, x_max, altura, fonte_escola)
    _rodape(draw, disciplina, numero, total, x0, x_max, altura)


def _layout_definicao(img, draw, titulo, topicos, destaque, disciplina, numero, total, dims):
    largura, altura, x0, x_max = dims
    _barra_lateral(draw, altura)
    _desenhar_tag(draw, destaque, x_max, 28)

    fonte_termo = _carregar_fonte(62, negrito=True)
    fonte_def   = _carregar_fonte(26)
    lmax        = x_max - x0

    y = 70
    for linha in _quebrar_linhas(draw, titulo.upper(), fonte_termo, lmax)[:2]:
        draw.text((x0, y), linha, font=fonte_termo, fill=ACCENT_COLOR)
        y += _alt(draw, fonte_termo) + 10
    y += 4
    draw.line([(x0, y), (x_max - 20, y)], fill=ACCENT_COLOR, width=3)
    y += 26

    for t in topicos[:3]:
        for linha in _quebrar_linhas(draw, t, fonte_def, lmax)[:2]:
            draw.text((x0, y), linha, font=fonte_def, fill=TEXT_COLOR)
            y += 34
        y += 8

    _rodape(draw, disciplina, numero, total, x0, x_max, altura)


def _layout_processo(img, draw, titulo, topicos, destaque, disciplina, numero, total, dims):
    largura, altura, x0, x_max = dims
    _barra_lateral(draw, altura)

    fonte_titulo = _carregar_fonte(38, negrito=True)
    fonte_etapa  = _carregar_fonte(26)
    fonte_num    = _carregar_fonte(32, negrito=True)
    lmax         = x_max - x0
    num_w        = draw.textbbox((0, 0), "9. ", font=fonte_num)[2]
    alt_e        = _alt(draw, fonte_etapa) + 6

    y = _titulo_linha(draw, titulo, x0, x_max, 56, fonte_titulo)

    for i, etapa in enumerate(topicos[:5]):
        etapa_limpa  = re.sub(r'^\s*\d+[.)]\s*', '', etapa).strip()
        linhas_etapa = _quebrar_linhas(draw, etapa_limpa, fonte_etapa, lmax - num_w)[:2]
        draw.text((x0, y - 2), f"{i + 1}.", font=fonte_num, fill=ACCENT_COLOR)
        for j, linha in enumerate(linhas_etapa):
            draw.text((x0 + num_w, y + j * alt_e), linha, font=fonte_etapa, fill=TEXT_COLOR)
        y += len(linhas_etapa) * alt_e + 10

        # Seta entre etapas
        if i < min(len(topicos), 5) - 1:
            draw.text((x0 + 6, y - 6), "↓", font=fonte_num, fill=ACCENT_COLOR)
            y += 26

    _rodape(draw, disciplina, numero, total, x0, x_max, altura)


def _layout_numero(img, draw, titulo, topicos, destaque, disciplina, numero, total, dims):
    largura, altura, x0, x_max = dims
    _barra_lateral(draw, altura)

    fonte_titulo = _carregar_fonte(36, negrito=True)
    fonte_big    = _carregar_fonte(80, negrito=True)
    fonte_ctx    = _carregar_fonte(26)
    lmax         = x_max - x0

    y = _titulo_linha(draw, titulo, x0, x_max, 56, fonte_titulo)

    stat_text = topicos[0] if topicos else ""
    m = re.search(r'[\d.,]+\s*%?', stat_text)
    if m:
        num_str = m.group().strip()
        ctx_str = stat_text.replace(m.group(), "", 1).strip(" -:") or (topicos[1] if len(topicos) > 1 else "")

        bbox_big = draw.textbbox((0, 0), num_str, font=fonte_big)
        bw = bbox_big[2] - bbox_big[0]
        draw.text((x0 + (lmax - bw) // 2, y), num_str, font=fonte_big, fill=ACCENT_COLOR)
        y += (bbox_big[3] - bbox_big[1]) + 12

        if ctx_str:
            for linha in _quebrar_linhas(draw, ctx_str, fonte_ctx, lmax)[:2]:
                bbox_c = draw.textbbox((0, 0), linha, font=fonte_ctx)
                cw = bbox_c[2] - bbox_c[0]
                draw.text((x0 + (lmax - cw) // 2, y), linha, font=fonte_ctx, fill=SUBTITLE_COLOR)
                y += 34
        y += 14

        # Tópicos adicionais
        fonte_extra = _carregar_fonte(22)
        fonte_marc  = _carregar_fonte(24, negrito=True)
        marc_w      = draw.textbbox((0, 0), MARCADOR + " ", font=fonte_marc)[2]
        for t in topicos[2:5]:
            for linha in _quebrar_linhas(draw, t, fonte_extra, lmax - marc_w)[:1]:
                draw.text((x0, y - 2), MARCADOR, font=fonte_marc, fill=ACCENT_COLOR)
                draw.text((x0 + marc_w, y), linha, font=fonte_extra, fill=TEXT_COLOR)
                y += 30
    else:
        # Sem número detectado: fallback para lista
        _bullets(
            draw, topicos, destaque, x0, x_max, y, altura - MARGEM_INFERIOR_AVATAR - y,
            _carregar_fonte(30), _carregar_fonte(30, negrito=True), _carregar_fonte(32, negrito=True),
        )

    _rodape(draw, disciplina, numero, total, x0, x_max, altura)


# ── Dispatcher ────────────────────────────────────────────────────────────────

_LAYOUTS = {
    TIPO_LISTA:        _layout_lista,
    TIPO_ABERTURA:     _layout_abertura,
    TIPO_ENCERRAMENTO: _layout_encerramento,
    TIPO_DEFINICAO:    _layout_definicao,
    TIPO_PROCESSO:     _layout_processo,
    TIPO_NUMERO:       _layout_numero,
}


def _gerar_slide_cena(cena, caminho_saida, disciplina, conteudo=None, numero=1, total=1):
    """Gera 1 slide PNG. Conteúdo ocupa quase a tela toda — o avatar é um PiP
    sobreposto no canto inferior esquerdo (ver compor_avatar_slides.py), por
    isso o texto usa MARGEM_INFERIOR_AVATAR para não ficar atrás dele."""
    largura, altura = 1280, 720
    area_w = int(largura * 0.97)
    x0, x_max = 70, area_w - 30

        # Fundo lousa com textura de giz
    img = Image.new("RGB", (largura, altura), BG_COLOR)
    noise = np.random.randint(0, 12, (altura // 4, largura // 4), dtype=np.uint8)
    noise_img = Image.fromarray(noise, mode='L')
    noise_img = noise_img.resize((largura, altura), Image.NEAREST)
    noise_img = noise_img.filter(ImageFilter.GaussianBlur(radius=1))
    noise_rgb = noise_img.convert("RGB")
    img = Image.blend(img, noise_rgb, alpha=0.10)
    draw = ImageDraw.Draw(img)


    titulo, topicos, destaque = _extrair_conteudo(cena, conteudo, disciplina)
    tipo = _detectar_tipo(cena, conteudo, numero - 1, total)
    _LAYOUTS.get(tipo, _layout_lista)(
        img, draw, titulo, topicos, destaque, disciplina, numero, total,
        (largura, altura, x0, x_max),
    )
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

    pasta_pai            = os.path.dirname(pasta_saida.rstrip("/\\"))
    caminho_content_json = os.path.join(pasta_pai, "slides_content.json")

    conteudos    = None
    openai_token = os.getenv("OPENAI_API_KEY")
    slides_md    = os.getenv("SLIDES_MD_CONTEXT", "")

    if os.path.isfile(caminho_content_json):
        try:
            with open(caminho_content_json, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached, list) and len(cached) == len(cenas):
                conteudos = cached
                print(f"   Reusando conteúdo de slides: {caminho_content_json}")
        except Exception:
            pass

    if conteudos is None:
        if openai_token and slides_md:
            try:
                from src.video_generator.slides_content_generator import gerar_conteudo_slides
                print(f"   Gerando conteúdo de slides via OpenAI ({len(cenas)} cenas)...")
                conteudos = gerar_conteudo_slides(slides_md, cenas, disciplina, openai_token)
                with open(caminho_content_json, "w", encoding="utf-8") as f:
                    json.dump(conteudos, f, indent=2, ensure_ascii=False)
                print(f"   Conteúdo salvo: {caminho_content_json}")
            except Exception as e:
                print(f"   [AVISO] Falha ao gerar conteúdo via OpenAI: {e}. Usando fallback.")
        elif not openai_token:
            print("   [AVISO] OPENAI_API_KEY ausente — usando fallback determinístico.")
        else:
            print("   [AVISO] SLIDES_MD_CONTEXT vazio — usando fallback determinístico.")

    total    = len(cenas)
    caminhos = []
    for i, cena in enumerate(cenas):
        caminho  = os.path.join(pasta_saida, f"slide_{i:03d}.png")
        conteudo = conteudos[i] if (conteudos and i < len(conteudos)) else None
        _gerar_slide_cena(cena, caminho, disciplina, conteudo, numero=i + 1, total=total)
        caminhos.append(os.path.abspath(caminho))

    print(f"   {len(caminhos)} slide(s) gerado(s) em: {pasta_saida}")
    return caminhos
