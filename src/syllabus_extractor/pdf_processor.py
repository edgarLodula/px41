import os
import re
import json
import fitz
import pdfplumber
import requests
from dotenv import load_dotenv
from src.syllabus_extractor.text_utils import limpar_texto, normalizar_campo
from src.syllabus_extractor.ocr_utils import extrair_texto_com_ocr

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


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
# PROCESSA PDF — usa Gemini para identificar e estruturar as disciplinas
# =========================
def processar_pdf(caminho_pdf: str) -> list[dict]:
    """
    Extrai texto do PDF com pdfplumber e usa o Gemini para identificar
    e estruturar todas as disciplinas.

    Retorna lista de dicts: { disciplina, ementa, conteudo, pagina }
    compatível com processar_semantico().
    """
    # 1. Extrai texto bruto
    texto_bruto = _extrair_texto_completo(caminho_pdf)
    total_paginas = _contar_paginas(caminho_pdf)
    print(f"📄 PDF aberto: {total_paginas} páginas")

    if not texto_bruto.strip():
        print("⚠️ Nenhum texto extraído. PDF pode ser uma imagem escaneada.")
        return []

    # 2. Gemini identifica e estrutura as disciplinas
    gemini_token = os.getenv("GEMINI_API_KEY", "")
    if not gemini_token:
        raise ValueError("GEMINI_API_KEY não configurada.")

    disciplinas = _gemini_extrair_disciplinas(texto_bruto, gemini_token)
    print(f"✅ {len(disciplinas)} disciplina(s) identificada(s) pelo Gemini")

    return disciplinas


def _contar_paginas(caminho_pdf: str) -> int:
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            return len(pdf.pages)
    except Exception:
        return 0


def _extrair_texto_completo(caminho_pdf: str) -> str:
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            return "\n\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        # fallback: PyMuPDF
        doc = fitz.open(caminho_pdf)
        return "\n\n".join(doc[i].get_text("text") for i in range(doc.page_count))


def _gemini_extrair_disciplinas(texto_bruto: str, token: str) -> list[dict]:
    """
    Envia o texto do PDF ao Gemini e recebe JSON estruturado com as disciplinas.
    """
    contexto = texto_bruto[:15000]

    prompt = f"""Você é um especialista em currículos escolares técnicos.

Analise o texto abaixo extraído de um PDF de currículo escolar e extraia TODAS as disciplinas encontradas.

Retorne APENAS um array JSON válido, sem nenhum texto antes ou depois, no formato:
[
  {{
    "disciplina": "nome completo da disciplina",
    "ementa": "texto da ementa (objetivo/descrição da disciplina)",
    "conteudo": "lista dos tópicos do conteúdo programático separados por ; ou newline",
    "pagina": 0
  }},
  ...
]

Regras:
- Inclua TODAS as disciplinas, sem pular nenhuma
- "ementa" deve capturar o objetivo ou descrição da disciplina
- "conteudo" deve capturar os tópicos/itens do conteúdo programático
- Se não encontrar ementa ou conteúdo para uma disciplina, use string vazia
- Ignore cabeçalhos institucionais (endereço, portaria, CNPJ, etc.)
- "pagina" pode ser 0 para todas

TEXTO DO PDF:
{contexto}

JSON:"""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8000},
    }

    for tentativa in range(3):
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}"
                f":generateContent?key={token}",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            texto = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Remove marcadores de código se presentes
            texto = re.sub(r"^```(?:json)?\s*", "", texto)
            texto = re.sub(r"\s*```$", "", texto)

            disciplinas = json.loads(texto)
            return disciplinas if isinstance(disciplinas, list) else []

        except Exception as e:
            if tentativa < 2:
                import time
                time.sleep(5 * (tentativa + 1))
            else:
                print(f"⚠️ Gemini falhou na extração de disciplinas: {e}")
                return []

    return []


# =========================
# PROCESSA SEMÂNTICO
# =========================
def processar_semantico(resultados: list[dict], nome_arquivo: str) -> list[dict]:
    base_final = []
    for i, item in enumerate(resultados):
        disciplina = normalizar_campo(item.get("disciplina", ""))
        ementa     = normalizar_campo(item.get("ementa", ""))
        conteudo   = normalizar_campo(item.get("conteudo", ""))

        base_final.append({
            "arquivo":         nome_arquivo,
            "pagina":          item.get("pagina", i),
            "chunk_id":        i,
            "disciplina":      disciplina,
            "ementa":          ementa,
            "conteudo":        conteudo,
            "texto_embedding": f"{disciplina}\n{ementa}\n{conteudo}",
        })
    return base_final