"""
Processador CSV → JSON.

Lê o CSV gerado por extrair_pdf_para_csv e converte para lista de registros
no formato esperado por gerar_markdowns e gerar_embeddings.

Cada tópico separado por '|' no campo Conteudo_Programatico vira um registro
individual (titulo_aula).
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Mapeamento das colunas do CSV para chaves internas
COLUNAS = {
    "curso": "Curso",
    "disciplina": "Disciplina",
    "ementa": "Ementa",
    "conteudo": "Conteudo_Programatico",
}

COLUNAS_OBRIGATORIAS = {"Disciplina", "Conteudo_Programatico"}


def normalizar_campo(valor) -> str:
    """Remove NaN e retorna string limpa."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(valor).strip()
    return "" if s.lower() in ("nan", "none", "") else s


def _verificar_colunas(df: pd.DataFrame, caminho: str) -> None:
    presentes = set(df.columns)
    ausentes = COLUNAS_OBRIGATORIAS - presentes
    if ausentes:
        raise ValueError(
            f"CSV '{caminho}' não possui colunas obrigatórias: {sorted(ausentes)}. "
            f"Colunas encontradas: {sorted(presentes)}"
        )


def extrair_base_csv(
    caminho_pdf: str,
    pasta_csv: str = "data/input/planilhas_geradas",
    pasta_json: str = "data/output/json",
) -> list[dict]:
    """
    Lê o CSV gerado por extrair_pdf_para_csv e converte para lista de registros.

    Salva um JSON por PDF em pasta_json e retorna a lista de registros.
    Retorna [] se o CSV não existir ou estiver vazio.
    """
    nome_base = Path(caminho_pdf).stem  # remove extensão
    caminho_csv = Path(pasta_csv) / (nome_base + ".csv")
    caminho_json = Path(pasta_json) / (nome_base + ".json")

    Path(pasta_json).mkdir(parents=True, exist_ok=True)

    if not caminho_csv.exists():
        logger.warning("CSV não encontrado: %s", caminho_csv)
        print(f"⚠️ CSV não encontrado: {caminho_csv}")
        return []

    registros: list[dict] = []

    try:
        with caminho_csv.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            colunas_csv = set(reader.fieldnames or [])
            ausentes = COLUNAS_OBRIGATORIAS - colunas_csv
            if ausentes:
                raise ValueError(
                    f"CSV '{caminho_csv}' não possui colunas obrigatórias: "
                    f"{sorted(ausentes)}. Encontradas: {sorted(colunas_csv)}"
                )

            for row_idx, linha in enumerate(reader):
                curso = " ".join((linha.get("Curso") or "").split()).strip()
                disciplina = " ".join((linha.get("Disciplina") or "").split()).strip()
                ementa = " ".join((linha.get("Ementa") or "").split()).strip()
                conteudo_raw = (linha.get("Conteudo_Programatico") or "").strip()

                if not disciplina:
                    continue

                topicos = [t.strip() for t in conteudo_raw.split("|") if t.strip()]
                if not topicos:
                    topicos = [disciplina]

                for aula_idx, topico in enumerate(topicos):
                    registros.append({
                        "arquivo": nome_base,
                        "pagina": row_idx,
                        "chunk_id": f"{row_idx}_{aula_idx}",
                        "curso": curso,
                        "disciplina": disciplina,
                        "ementa": ementa,
                        "aula": aula_idx + 1,
                        "titulo_aula": topico,
                        "conteudo": topico,
                        "conceitos_chave": "",
                        "exemplos": "",
                        "exercicios": "",
                        "texto_embedding": f"{curso}\n{disciplina}\n{ementa}\n{topico}",
                    })

    except (csv.Error, UnicodeDecodeError) as exc:
        raise ValueError(f"Erro ao ler CSV '{caminho_csv}': {exc}") from exc

    with caminho_json.open("w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)

    n_disc = len({r["disciplina"] for r in registros})
    logger.info(
        "JSON salvo: %s (%d tópicos | %d disciplinas)", caminho_json, len(registros), n_disc
    )
    print(f"✅ JSON salvo: {caminho_json} ({len(registros)} tópicos | {n_disc} disciplinas)")
    return registros


# ---------------------------------------------------------------------------
# ENTRYPOINT (CLI mínimo)
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Converte CSV de conteúdo programático para JSON."
    )
    p.add_argument("caminho_pdf", help="Caminho do PDF de origem (para nomear o CSV/JSON).")
    p.add_argument(
        "--pasta-csv",
        default="data/input/planilhas_geradas",
        help="Diretório onde o CSV está salvo.",
    )
    p.add_argument(
        "--pasta-json",
        default="data/output/json",
        help="Diretório onde o JSON será salvo.",
    )
    args = p.parse_args()

    registros = extrair_base_csv(args.caminho_pdf, args.pasta_csv, args.pasta_json)
    if not registros:
        print("Nenhum registro extraído.")
    else:
        print(f"{len(registros)} registros extraídos.")


if __name__ == "__main__":
    _cli()
