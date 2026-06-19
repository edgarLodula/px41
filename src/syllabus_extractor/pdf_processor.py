"""
Processador de PDFs via PyMuPDF (fitz) com fallback OCR.

`processar_pdf()` extrai texto de cada página, detecta a disciplina,
agrupa páginas da mesma disciplina e retorna lista de dicionários.
"""
import re
import logging
import fitz  # PyMuPDF

from src.syllabus_extractor.text_utils import limpar_texto, normalizar_campo
from src.syllabus_extractor.ocr_utils import extrair_texto_com_ocr, tesseract_disponivel

logger = logging.getLogger(__name__)

_MIN_CHARS_TEXTO_NATIVO = 30


# ---------------------------------------------------------------------------
# EXTRAÇÃO DE TEXTO DE UMA PÁGINA
# ---------------------------------------------------------------------------

def extrair_texto_pagina(page) -> str:
    """Extrai texto nativo; usa OCR como fallback se texto insuficiente."""
    texto = page.get_text("text").strip()
    if len(texto) >= _MIN_CHARS_TEXTO_NATIVO:
        return texto

    if tesseract_disponivel():
        try:
            return extrair_texto_com_ocr(page)
        except Exception as exc:
            logger.warning("OCR falhou na página %d: %s", page.number, exc)
    return ""


# ---------------------------------------------------------------------------
# HEURÍSTICAS DE EXTRAÇÃO DE CAMPOS
# ---------------------------------------------------------------------------

def detectar_disciplina(texto: str) -> str:
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        if re.match(r"^\d+[\.\)]\s", linha):
            continue
        if len(linha) > 120:
            continue
        return linha
    return "Disciplina Desconhecida"


def _extrair_ementa(texto: str) -> str:
    match = re.search(
        r"1[\.\)]\s+Introdu[çc][aã]o[^\n]*\n(.*?)(?=\n\s*\d+[\.\)]\s|\Z)",
        texto, re.DOTALL | re.IGNORECASE,
    )
    if match:
        return limpar_texto(match.group(1)[:800])
    return limpar_texto(texto[:400])


def _extrair_conteudo(texto: str) -> str:
    match = re.search(
        r"3[\.\)]\s+[^\n]*\n(.*?)(?=\n\s*\d+[\.\)]\s|\Z)",
        texto, re.DOTALL | re.IGNORECASE,
    )
    if match:
        return limpar_texto(match.group(1)[:2_000])
    return limpar_texto(texto[:2_000])


def extrair_secoes(texto: str) -> dict[str, str]:
    pattern = re.compile(r"(?m)^\s*(\d+[\.\)]\s+[^\n]+)")
    partes = pattern.split(texto)
    secoes: dict[str, str] = {}
    i = 1
    while i < len(partes) - 1:
        titulo = partes[i].strip()
        conteudo = partes[i + 1].strip() if i + 1 < len(partes) else ""
        secoes[titulo] = conteudo
        i += 2
    return secoes


# ---------------------------------------------------------------------------
# PROCESSAMENTO PRINCIPAL
# ---------------------------------------------------------------------------

def processar_pdf(caminho_pdf: str) -> list[dict]:
    """
    Extrai conteúdo estruturado do PDF página a página.

    Agrupa páginas por disciplina detectada e retorna lista de dicts com:
      arquivo, pagina, chunk_id, disciplina, ementa, conteudo, texto_embedding.

    Nunca retorna None; sempre retorna list[dict] (pode ser vazia).
    """
    base_final: list[dict] = []
    doc = None

    try:
        doc = fitz.open(caminho_pdf)
        logger.info("PDF aberto: %s (%d páginas)", caminho_pdf, doc.page_count)
        print(f"📄 PDF aberto: {doc.page_count} páginas")

        disciplina_atual: str | None = None
        texto_acumulado = ""

        for num_pag, page in enumerate(doc):
            texto_pag = extrair_texto_pagina(page)
            if not texto_pag.strip():
                continue

            disc_detectada = detectar_disciplina(texto_pag)

            if disc_detectada != disciplina_atual:
                # Salva disciplina anterior
                if disciplina_atual and texto_acumulado.strip():
                    base_final.append(_montar_registro(
                        caminho_pdf, num_pag - 1,
                        disciplina_atual, texto_acumulado,
                        len(base_final),
                    ))
                disciplina_atual = disc_detectada
                texto_acumulado = texto_pag
            else:
                texto_acumulado += "\n" + texto_pag

        # Salva última disciplina
        if disciplina_atual and texto_acumulado.strip():
            base_final.append(_montar_registro(
                caminho_pdf, doc.page_count - 1,
                disciplina_atual, texto_acumulado,
                len(base_final),
            ))

    except Exception as exc:
        logger.error("Erro ao processar '%s': %s", caminho_pdf, exc)
        raise
    finally:
        if doc is not None:
            doc.close()

    return base_final


def _montar_registro(
    caminho_pdf: str,
    pagina: int,
    disciplina: str,
    texto: str,
    chunk_id: int,
) -> dict:
    import os
    nome_arquivo = os.path.basename(caminho_pdf)
    ementa = _extrair_ementa(texto)
    conteudo = _extrair_conteudo(texto)
    return {
        "arquivo": nome_arquivo,
        "pagina": pagina,
        "chunk_id": chunk_id,
        "disciplina": normalizar_campo(disciplina),
        "ementa": normalizar_campo(ementa),
        "conteudo": normalizar_campo(conteudo),
        "texto_embedding": f"{disciplina}\n{ementa}\n{conteudo}",
    }


# ---------------------------------------------------------------------------
# PÓS-PROCESSAMENTO SEMÂNTICO (preservado para compatibilidade)
# ---------------------------------------------------------------------------

def processar_semantico(resultados: list[dict], nome_arquivo: str) -> list[dict]:
    base_final: list[dict] = []
    for i, item in enumerate(resultados):
        disciplina = normalizar_campo(item["disciplina"])
        ementa = normalizar_campo(item["ementa"])
        conteudo = normalizar_campo(item["conteudo"])
        base_final.append({
            "arquivo": nome_arquivo,
            "pagina": item["pagina"],
            "chunk_id": i,
            "disciplina": disciplina,
            "ementa": ementa,
            "conteudo": conteudo,
            "texto_embedding": f"{disciplina}\n{ementa}\n{conteudo}",
        })
    return base_final
