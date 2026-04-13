import re
import fitz
from src.syllabus_extractor.text_utils import limpar_texto, normalizar_campo
from src.syllabus_extractor.ocr_utils import extrair_texto_com_ocr


# =========================
# EXTRAÇÃO DE TEXTO DA PÁGINA
# =========================
def extrair_texto_pagina(page):
    texto = page.get_text("text").strip()
    if len(texto) > 30:
        return texto
    try:
        return extrair_texto_com_ocr(page)
    except Exception:
        return ""


# =========================
# DETECTA NOME DA DISCIPLINA
# Heurística: primeira linha não vazia com menos de 120 chars e sem número no início
# =========================
def detectar_disciplina(texto: str) -> str:
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        # Pula linhas que parecem cabeçalhos de seção (ex: "1. Introdução")
        if re.match(r"^\d+[\.\)]\s", linha):
            continue
        # Pula linhas muito longas (parágrafos)
        if len(linha) > 120:
            continue
        return linha
    return "Disciplina Desconhecida"


# =========================
# EXTRAI SEÇÕES DO TEXTO
# Divide o texto nas seções numeradas (1. ..., 2. ..., 3. ...)
# =========================
def extrair_secoes(texto: str) -> dict[str, str]:
    pattern = re.compile(r"(?m)^\s*(\d+[\.\)]\s+[^\n]+)")
    partes = pattern.split(texto)

    secoes = {}
    i = 1
    while i < len(partes) - 1:
        titulo = partes[i].strip()
        conteudo = partes[i + 1].strip() if i + 1 < len(partes) else ""
        secoes[titulo] = conteudo
        i += 2

    return secoes


# =========================
# PROCESSA PDF — extrai por disciplina (agrupa páginas da mesma disciplina)
# =========================
def processar_pdf(caminho_pdf: str) -> list[dict]:
    doc = fitz.open(caminho_pdf)
    base_final = []

    print(f"📄 PDF aberto: {doc.page_count} páginas")

    disciplina_atual = None
    texto_acumulado = ""

    for i, page in enumerate(doc):
        print(f"  Processando página {i + 1}/{doc.page_count}...")
        texto = extrair_texto_pagina(page)

        if not texto.strip():
            continue

        # Detecta se é início de nova disciplina
        # Heurística: se o texto começa com um título curto (< 120 chars) antes da primeira seção numerada
        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        primeira_linha = linhas[0] if linhas else ""

        tem_nova_disciplina = (
            primeira_linha
            and len(primeira_linha) < 120
            and not re.match(r"^\d+[\.\)]\s", primeira_linha)
            and "Documento de Estudo" not in primeira_linha
        )

        if tem_nova_disciplina and disciplina_atual and disciplina_atual != primeira_linha:
            # Salva a disciplina anterior
            if texto_acumulado.strip():
                base_final.append({
                    "pagina": i,
                    "disciplina": disciplina_atual,
                    "ementa": _extrair_ementa(texto_acumulado),
                    "conteudo": _extrair_conteudo(texto_acumulado),
                })
            disciplina_atual = primeira_linha
            texto_acumulado = texto
        else:
            if disciplina_atual is None:
                disciplina_atual = detectar_disciplina(texto)
            texto_acumulado += "\n" + texto

    # Salva a última disciplina
    if disciplina_atual and texto_acumulado.strip():
        base_final.append({
            "pagina": doc.page_count,
            "disciplina": disciplina_atual,
            "ementa": _extrair_ementa(texto_acumulado),
            "conteudo": _extrair_conteudo(texto_acumulado),
        })

    doc.close()
    print(f"✅ {len(base_final)} disciplinas extraídas")
    return base_final


# =========================
# EXTRAI EMENTA
# Pega a seção de "Introdução" ou "Objetivos" como ementa
# =========================
def _extrair_ementa(texto: str) -> str:
    # Tenta pegar a seção "1. Introdução"
    match = re.search(
        r"1[\.\)]\s+Introdu[çc][aã]o[^\n]*\n(.*?)(?=\n\s*\d+[\.\)]\s|\Z)",
        texto, re.DOTALL | re.IGNORECASE
    )
    if match:
        return limpar_texto(match.group(1)[:800])

    # Fallback: primeiros 400 chars do texto
    return limpar_texto(texto[:400])


# =========================
# EXTRAI CONTEÚDO
# Pega a seção "3. Explicação dos Tópicos" ou o corpo principal
# =========================
def _extrair_conteudo(texto: str) -> str:
    # Tenta pegar seção 3 (Tópicos/Conteúdo)
    match = re.search(
        r"3[\.\)]\s+[^\n]*\n(.*?)(?=\n\s*\d+[\.\)]\s|\Z)",
        texto, re.DOTALL | re.IGNORECASE
    )
    if match:
        return limpar_texto(match.group(1)[:2000])

    # Fallback: texto completo truncado
    return limpar_texto(texto[:2000])


# =========================
# PROCESSA SEMÂNTICO
# =========================
def processar_semantico(resultados: list[dict], nome_arquivo: str) -> list[dict]:
    base_final = []
    for i, item in enumerate(resultados):
        disciplina = normalizar_campo(item["disciplina"])
        ementa     = normalizar_campo(item["ementa"])
        conteudo   = normalizar_campo(item["conteudo"])

        base_final.append({
            "arquivo":         nome_arquivo,
            "pagina":          item["pagina"],
            "chunk_id":        i,
            "disciplina":      disciplina,
            "ementa":          ementa,
            "conteudo":        conteudo,
            "texto_embedding": f"{disciplina}\n{ementa}\n{conteudo}",
        })
    return base_final