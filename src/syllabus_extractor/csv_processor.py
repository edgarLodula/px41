"""
PIPELINE: CSV → JSON
Substitui o fluxo: processar_pdf() + processar_semantico()
O JSON gerado tem as MESMAS chaves do código original,
então tudo que consome o JSON (gerar_markdowns, etc.) continua funcionando.
"""

import os
import json
import pandas as pd
import pdfplumber

# ─── CONFIG ────────────────────────────────────────────────────────────────────
CSV_PATH    = "../../data/input/planilhas_geradas/planilha.csv"
PASTA_JSON  = "../../data/output/json"
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


def extrair_base_csv(CAMINHO_PDF):
    """
    Substitui o extrair_base() original.
    Agora extrai direto do PDF em vez de ler CSV manual.
    """
    os.makedirs(PASTA_JSON, exist_ok=True)

    if not os.path.exists(CAMINHO_PDF):
        print(f"⚠️  PDF não encontrado em: {CAMINHO_PDF}")
        return

    print(f"\n📄 Processando PDF: {CAMINHO_PDF}")

    registros = []
    with pdfplumber.open(CAMINHO_PDF) as pdf:
        for pagina in pdf.pages:
            for tabela in (pagina.extract_tables() or []):
                for linha in tabela:
                    if not linha[0] or linha[0].strip() in ("", "Disciplina"):
                        continue

                    registros.append({
                        "curso":                  "Técnico em Enfermagem",
                        "disciplina":             (linha[0] or "").strip(),
                        "ementa":                 (linha[1] or "").strip(),
                        "conteudo_programatico": [
                            c.strip()
                            for c in (linha[2] or "").split("\n")
                            if c.strip()
                        ]
                    })

    with open(CAMINHO_JSON, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)

    print(f"\n✅ JSON salvo em: {CAMINHO_JSON}  ({len(registros)} registros)")


if __name__ == "__main__":
    extrair_base_csv()