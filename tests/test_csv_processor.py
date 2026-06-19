"""Testes do processador CSV → JSON."""
import csv
import json
import os
import tempfile
import pytest

from src.syllabus_extractor.csv_processor import extrair_base_csv, normalizar_campo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _escrever_csv(pasta_csv: str, nome_base: str, linhas: list[dict]) -> str:
    os.makedirs(pasta_csv, exist_ok=True)
    caminho = os.path.join(pasta_csv, nome_base + ".csv")
    colunas = list(linhas[0].keys()) if linhas else ["Disciplina", "Conteudo_Programatico"]
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        w.writerows(linhas)
    return caminho


def _run(nome_base: str, linhas: list[dict], pasta_raiz: str):
    pasta_csv = os.path.join(pasta_raiz, "csv")
    pasta_json = os.path.join(pasta_raiz, "json")
    _escrever_csv(pasta_csv, nome_base, linhas)
    caminho_pdf = os.path.join("qualquer", "pasta", nome_base + ".pdf")
    return extrair_base_csv(caminho_pdf, pasta_csv, pasta_json)


# ---------------------------------------------------------------------------
# normalizar_campo
# ---------------------------------------------------------------------------

def test_normalizar_campo_retorna_vazio_para_none():
    assert normalizar_campo(None) == ""


def test_normalizar_campo_retorna_vazio_para_nan():
    assert normalizar_campo(float("nan")) == ""


def test_normalizar_campo_retorna_string():
    assert normalizar_campo("  Disciplina  ") == "Disciplina"


# ---------------------------------------------------------------------------
# extrair_base_csv — CSV válido
# ---------------------------------------------------------------------------

def test_extrai_registros_simples():
    with tempfile.TemporaryDirectory() as d:
        linhas = [
            {"Disciplina": "Anatomia", "Conteudo_Programatico": "Ossos | Músculos",
             "Curso": "Enfermagem", "Ementa": "Estudo do corpo"},
        ]
        registros = _run("curso_teste", linhas, d)

    assert len(registros) == 2  # dois tópicos
    assert registros[0]["titulo_aula"] == "Ossos"
    assert registros[1]["titulo_aula"] == "Músculos"


def test_todos_registros_tem_campos_obrigatorios():
    with tempfile.TemporaryDirectory() as d:
        linhas = [
            {"Disciplina": "D1", "Conteudo_Programatico": "T1 | T2",
             "Curso": "C", "Ementa": "E"},
        ]
        registros = _run("pdf1", linhas, d)

    campos = {"arquivo", "disciplina", "ementa", "aula", "titulo_aula", "conteudo",
              "texto_embedding", "curso"}
    for r in registros:
        for c in campos:
            assert c in r, f"Campo ausente: {c}"


def test_gera_json_na_pasta_saida():
    with tempfile.TemporaryDirectory() as d:
        pasta_json = os.path.join(d, "json")
        pasta_csv = os.path.join(d, "csv")
        linhas = [{"Disciplina": "D1", "Conteudo_Programatico": "T1"}]
        _escrever_csv(pasta_csv, "meu_pdf", linhas)
        extrair_base_csv(os.path.join("x", "meu_pdf.pdf"), pasta_csv, pasta_json)
        json_path = os.path.join(pasta_json, "meu_pdf.json")
        assert os.path.isfile(json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            dados = json.load(f)
        assert isinstance(dados, list)
        assert len(dados) == 1


def test_disciplina_vazia_ignorada():
    with tempfile.TemporaryDirectory() as d:
        linhas = [
            {"Disciplina": "", "Conteudo_Programatico": "T1"},
            {"Disciplina": "D2", "Conteudo_Programatico": "T2"},
        ]
        registros = _run("pdf", linhas, d)
    assert all(r["disciplina"] for r in registros)
    assert len(registros) == 1


def test_sem_topicos_usa_nome_disciplina():
    """Se Conteudo_Programatico está vazio, usa a disciplina como tópico único."""
    with tempfile.TemporaryDirectory() as d:
        linhas = [{"Disciplina": "BioQuímica", "Conteudo_Programatico": ""}]
        registros = _run("pdf", linhas, d)
    assert len(registros) == 1
    assert registros[0]["titulo_aula"] == "BioQuímica"


def test_csv_nao_encontrado_retorna_lista_vazia():
    with tempfile.TemporaryDirectory() as d:
        pasta_json = os.path.join(d, "json")
        os.makedirs(pasta_json, exist_ok=True)
        registros = extrair_base_csv("nao_existe.pdf", d, pasta_json)
    assert registros == []


# ---------------------------------------------------------------------------
# extrair_base_csv — colunas ausentes
# ---------------------------------------------------------------------------

def test_coluna_disciplina_ausente_raise_valueerror():
    with tempfile.TemporaryDirectory() as d:
        pasta_csv = os.path.join(d, "csv")
        pasta_json = os.path.join(d, "json")
        os.makedirs(pasta_csv)
        os.makedirs(pasta_json)
        # CSV sem a coluna Disciplina
        caminho = os.path.join(pasta_csv, "sem_disc.csv")
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["Conteudo_Programatico"])
            w.writeheader()
            w.writerow({"Conteudo_Programatico": "T1"})

        with pytest.raises(ValueError, match="Disciplina"):
            extrair_base_csv("sem_disc.pdf", pasta_csv, pasta_json)


def test_coluna_conteudo_ausente_raise_valueerror():
    with tempfile.TemporaryDirectory() as d:
        pasta_csv = os.path.join(d, "csv")
        pasta_json = os.path.join(d, "json")
        os.makedirs(pasta_csv)
        os.makedirs(pasta_json)
        caminho = os.path.join(pasta_csv, "sem_cont.csv")
        with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["Disciplina"])
            w.writeheader()
            w.writerow({"Disciplina": "D1"})

        with pytest.raises(ValueError, match="Conteudo_Programatico"):
            extrair_base_csv("sem_cont.pdf", pasta_csv, pasta_json)


# ---------------------------------------------------------------------------
# Múltiplas disciplinas
# ---------------------------------------------------------------------------

def test_multiplas_disciplinas_geram_registros_separados():
    with tempfile.TemporaryDirectory() as d:
        linhas = [
            {"Disciplina": "D1", "Conteudo_Programatico": "T1"},
            {"Disciplina": "D2", "Conteudo_Programatico": "T2 | T3"},
        ]
        registros = _run("pdf", linhas, d)

    disciplinas = {r["disciplina"] for r in registros}
    assert "D1" in disciplinas
    assert "D2" in disciplinas
    assert len(registros) == 3  # 1 + 2
