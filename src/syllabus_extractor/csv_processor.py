"""
PIPELINE: CSV → JSON
Substitui o fluxo: processar_pdf() + processar_semantico()
O JSON gerado tem as MESMAS chaves do código original,
então tudo que consome o JSON (gerar_markdowns, etc.) continua funcionando.
"""

import os
import json
import csv
import pandas as pd
import pdfplumber

# ─── CONFIG ────────────────────────────────────────────────────────────────────
CSV_PATH    = "../../data/input/planilhas_geradas/Tabela_Conteudo_Programatico_Tecnico_Eletrotecnica.docx.csv"
PASTA_JSON  = "../../data/output/json"
PASTA_CSV = "../../data/input/planilhas_geradas"
CAMINHO_JSON = os.path.join(PASTA_JSON, "base_curso.json")
# ───────────────────────────────────────────────────────────────────────────────

# Mapeamento exato das colunas do CSV
COLUNAS = {
    "curso":        "Curso",
    "disciplina":   "Disciplina",
    "aula":         "Aula",
    "titulo_aula":  "Título da Aula",
    "objetivo":     "Objetivo de Aprendizagem",   # → ementa
    "conteudo":     "Conteúdo Estruturado",        # → conteudo
    "conceitos":    "Conceitos-Chave",
    "exemplos":     "Exemplos Práticos",
    "exercicios":   "Exercícios",
    "dificuldade":  "Nível de Dificuldade",
    "prereqs":      "Pré-requisitos",
    "carga":        "Carga Horária",
    "roteiro":      "Roteiro de Vídeo",
    "referencias":  "Referências Técnicas",
}


def normalizar_campo(valor) -> str:
    """Remove NaN e retorna string limpa — igual ao normalizar_campo() original."""
    if pd.isna(valor) or str(valor).strip().lower() in ("nan", "none", ""):
        return ""
    return str(valor).strip()


def ler_csv(csv_path: str) -> list[dict]:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    # Remove linhas sem Disciplina (totalizadores / rodapé)
    col_disc = COLUNAS["disciplina"]
    df = df[df[col_disc].notna() & (df[col_disc].str.strip() != "")]

    registros = []
    for idx, row in df.iterrows():

        disciplina  = normalizar_campo(row.get(COLUNAS["disciplina"], ""))
        ementa      = normalizar_campo(row.get(COLUNAS["objetivo"], ""))
        conteudo    = normalizar_campo(row.get(COLUNAS["conteudo"], ""))

        registros.append({
            # ── chaves que o código original já usa ──────────────────────────
            "arquivo":          os.path.basename(csv_path),
            "pagina":           idx,
            "chunk_id":         idx,
            "disciplina":       disciplina,
            "ementa":           ementa,
            "conteudo":         conteudo,
            "texto_embedding":  f"{disciplina}\n{ementa}\n{conteudo}",

            # ── chaves extras do CSV (não quebram nada, só enriquecem) ───────
            "curso":            normalizar_campo(row.get(COLUNAS["curso"], "")),
            "aula":             normalizar_campo(row.get(COLUNAS["aula"], "")),
            "titulo_aula":      normalizar_campo(row.get(COLUNAS["titulo_aula"], "")),
            "conceitos_chave":  normalizar_campo(row.get(COLUNAS["conceitos"], "")),
            "exemplos":         normalizar_campo(row.get(COLUNAS["exemplos"], "")),
            "exercicios":       normalizar_campo(row.get(COLUNAS["exercicios"], "")),
            "dificuldade":      normalizar_campo(row.get(COLUNAS["dificuldade"], "")),
            "prereqs":          normalizar_campo(row.get(COLUNAS["prereqs"], "")),
            "carga_horaria":    normalizar_campo(row.get(COLUNAS["carga"], "")),
            "roteiro":          normalizar_campo(row.get(COLUNAS["roteiro"], "")),
            "referencias":      normalizar_campo(row.get(COLUNAS["referencias"], "")),
        })

    print(f"✅ CSV lido: {len(registros)} registros encontrados")
    return registros

def transformar_csv_em_json(nome_csv: str, nome_json: str):
    os.makedirs(PASTA_JSON, exist_ok=True)

    caminho_csv = os.path.join(PASTA_CSV, nome_csv)
    caminho_json = os.path.join(PASTA_JSON, nome_json)

    if not os.path.exists(caminho_csv):
        print(f"⚠️ CSV não encontrado: {caminho_csv}")
        return

    registros = []

    with open(caminho_csv, "r", encoding="utf-8-sig") as arquivo_csv:
        leitor = csv.DictReader(arquivo_csv)

        for linha in leitor:
            registro = {
                "curso": linha.get("curso", "").strip(),
                "disciplina": linha.get("disciplina", "").strip(),
                "ementa": linha.get("ementa", "").strip(),
                "conteudo_programatico": [
                    item.strip()
                    for item in linha.get("conteudo_programatico", "").split("\n")
                    if item.strip()
                ]
            }

            registros.append(registro)

    # estrutura final do JSON
    estrutura_final = {
        "total_registros": len(registros),
        "dados": registros
    }

    with open(caminho_json, "w", encoding="utf-8") as arquivo_json:
        json.dump(estrutura_final, arquivo_json, ensure_ascii=False, indent=2)

    print(f"✅ JSON salvo em: {caminho_json}")
    print(f"📦 {len(registros)} registros convertidos")

def extrair_base_csv(
    caminho_pdf: str,
    pasta_csv: str = "data/input/planilhas_geradas",
    pasta_json: str = "data/output/json"
) -> list:
    """
    Lê o CSV gerado por extrair_pdf_para_csv (colunas: Curso, Disciplina, Ementa,
    Conteudo_Programatico) e converte para lista de registros no formato esperado
    por gerar_markdowns e gerar_embeddings.

    Cada tópico separado por '|' no Conteudo_Programatico vira um registro
    individual (titulo_aula), permitindo que gerar_markdowns gere uma seção
    por tópico dentro da disciplina.

    Salva um JSON por PDF em pasta_json e retorna a lista de registros.
    """
    nome_base = os.path.basename(caminho_pdf).replace(".pdf", "")
    caminho_csv = os.path.join(pasta_csv, nome_base + ".csv")
    caminho_json = os.path.join(pasta_json, nome_base + ".json")

    os.makedirs(pasta_json, exist_ok=True)

    if not os.path.exists(caminho_csv):
        print(f"⚠️ CSV não encontrado: {caminho_csv}")
        return []

    registros = []

    with open(caminho_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_idx, linha in enumerate(reader):
            curso        = linha.get("Curso", "").strip()
            disciplina   = linha.get("Disciplina", "").strip()
            ementa       = linha.get("Ementa", "").strip()
            conteudo_raw = linha.get("Conteudo_Programatico", "").strip()

            if not disciplina:
                continue

            # Cada item separado por "|" vira um tópico/aula independente
            topicos = [t.strip() for t in conteudo_raw.split("|") if t.strip()]
            if not topicos:
                topicos = [disciplina]

            for aula_idx, topico in enumerate(topicos):
                registros.append({
                    "arquivo":         nome_base,
                    "pagina":          row_idx,
                    "chunk_id":        f"{row_idx}_{aula_idx}",
                    "curso":           curso,
                    "disciplina":      disciplina,
                    "ementa":          ementa,
                    "aula":            aula_idx + 1,
                    "titulo_aula":     topico,
                    "conteudo":        topico,
                    "conceitos_chave": "",
                    "exemplos":        "",
                    "exercicios":      "",
                    "texto_embedding": f"{curso}\n{disciplina}\n{ementa}\n{topico}",
                })

    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)

    n_disc = len(set(r["disciplina"] for r in registros))
    print(f"✅ JSON salvo: {caminho_json} ({len(registros)} tópicos | {n_disc} disciplinas)")
    return registros


if __name__ == "__main__":
    transformar_csv_em_json()