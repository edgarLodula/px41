import fitz
from src.syllabus_extractor.text_utils import limpar_texto, normalizar_campo
from src.syllabus_extractor.ocr_utils import extrair_texto_com_ocr

def extrair_texto_pagina(page):
    texto = page.get_text("text").strip()
    if len(texto) > 30:
        return texto
    return extrair_texto_com_ocr(page)

def processar_pdf(caminho_pdf):
    doc = fitz.open(caminho_pdf)
    base_final = []

    for i, page in enumerate(doc):
        tables = page.find_tables()

        for table in tables:
            rows = table.extract()

            for row in rows:
                if not row or len(row) < 3:
                    continue

                disciplina = limpar_texto(row[0] or "")
                ementa     = limpar_texto(row[1] or "")
                conteudo   = limpar_texto(row[2] or "")

                if disciplina.lower() in ("disciplina", ""):
                    continue

                base_final.append({
                    "pagina": i + 1,
                    "disciplina": disciplina,
                    "ementa": ementa,
                    "conteudo": conteudo,
                })

    doc.close()
    return base_final

def processar_semantico(resultados, nome_arquivo):
    base_final = []

    for i, item in enumerate(resultados):
        disciplina = normalizar_campo(item['disciplina'])
        ementa     = normalizar_campo(item['ementa'])
        conteudo   = normalizar_campo(item['conteudo'])

        base_final.append({
            "arquivo": nome_arquivo,
            "pagina": item["pagina"],
            "chunk_id": i,
            "disciplina": disciplina,
            "ementa": ementa,
            "conteudo": conteudo,
            "texto_embedding": f"{disciplina}\n{ementa}\n{conteudo}"
        })

    return base_final