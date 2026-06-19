"""Testes do gerador de Markdown (aluno + professor, retomada, erros)."""
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from src.output_formatter.markdown_generator import (
    gerar_markdowns,
    _par_completo,
    _escrever_atomico,
    _sanitizar_nome_arquivo,
    juntar_topicos_formatado,
    texto_para_markdown,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_minima(area: str = "tecnico_enfermagem") -> list[dict]:
    return [
        {
            "arquivo": "curso_teste",
            "curso": "Curso Teste",
            "disciplina": "Disciplina Alpha",
            "ementa": "Ementa da disciplina",
            "aula": 1,
            "titulo_aula": "Tópico 1",
            "conteudo": "Conteúdo do tópico",
            "area": area,
            "texto_embedding": "Disciplina Alpha Tópico 1",
        }
    ]


def _client_fake(resposta: str = "Conteúdo gerado"):
    c = MagicMock()
    c.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=resposta))]
    )
    return c


def _model_fake():
    import numpy as np
    m = MagicMock()
    m.encode.return_value = np.random.rand(1, 4).astype("float32")
    return m


def _buscar_fake(query, model, index, base, filtro_area=None, **kw):
    return []


def _gerar_doc_fake(client, disciplina, ementa, conteudo, contexto, profile):
    return f"Conteúdo fake para {disciplina}"


def _gerar_topico_fake(client, disciplina, topico, contexto, profile):
    return f"Conteúdo do tópico {topico}"


def _gerar_questoes_fake(client, disciplina, topico, contexto, profile):
    return "Questão aluno", "Gabarito professor"


def _rodar_geracao(base, pasta, force=False):
    with (
        patch("src.output_formatter.markdown_generator.gerar_topico", _gerar_topico_fake),
        patch("src.output_formatter.markdown_generator.gerar_questoes_topico", _gerar_questoes_fake),
    ):
        return gerar_markdowns(
            base_geral=base,
            buscar_chunks=_buscar_fake,
            gerar_documento=_gerar_doc_fake,
            model=_model_fake(),
            index=None,
            gemini=_client_fake(),
            pasta_saida=pasta,
            force=force,
            sleep_fn=lambda s: None,
        )


# ---------------------------------------------------------------------------
# _par_completo
# ---------------------------------------------------------------------------

def test_par_completo_quando_ambos_existem():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "aluno.md")
        p = os.path.join(d, "professor.md")
        for f in (a, p):
            with open(f, "w") as fh:
                fh.write("x" * 200)
        assert _par_completo(a, p)


def test_par_incompleto_quando_falta_professor():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "aluno.md")
        with open(a, "w") as fh:
            fh.write("x" * 200)
        assert not _par_completo(a, os.path.join(d, "professor.md"))


def test_par_incompleto_quando_arquivo_muito_pequeno():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "aluno.md")
        p = os.path.join(d, "professor.md")
        for f in (a, p):
            with open(f, "w") as fh:
                fh.write("x")  # menos de 100 bytes
        assert not _par_completo(a, p)


# ---------------------------------------------------------------------------
# _escrever_atomico
# ---------------------------------------------------------------------------

def test_escrever_atomico_cria_arquivo():
    with tempfile.TemporaryDirectory() as d:
        caminho = os.path.join(d, "saida.txt")
        _escrever_atomico(caminho, "conteúdo de teste")
        assert os.path.isfile(caminho)
        with open(caminho, "r", encoding="utf-8") as f:
            assert f.read() == "conteúdo de teste"


def test_escrever_atomico_cria_diretorios():
    with tempfile.TemporaryDirectory() as d:
        caminho = os.path.join(d, "subdir", "nested", "arquivo.txt")
        _escrever_atomico(caminho, "ok")
        assert os.path.isfile(caminho)


# ---------------------------------------------------------------------------
# _sanitizar_nome_arquivo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entrada", [
    "Disciplina Normal",
    "Disc: Especial / Barra",
    "Nome com   espaços   multiplos",
])
def test_sanitizar_nome_arquivo_sem_espacos(entrada):
    resultado = _sanitizar_nome_arquivo(entrada)
    assert " " not in resultado
    assert len(resultado) > 0


# ---------------------------------------------------------------------------
# Geração completa
# ---------------------------------------------------------------------------

def test_gera_arquivos_aluno_e_professor():
    base = _base_minima()
    with tempfile.TemporaryDirectory() as pasta:
        resultados = _rodar_geracao(base, pasta)
        r = resultados[0]
        assert not r.erro, f"Erro inesperado: {r.erro}"
        assert os.path.isfile(r.caminho_aluno)
        assert os.path.isfile(r.caminho_professor)


def test_professor_contem_gabarito():
    base = _base_minima()
    with tempfile.TemporaryDirectory() as pasta:
        resultados = _rodar_geracao(base, pasta)
        r = resultados[0]
        with open(r.caminho_professor, "r", encoding="utf-8") as f:
            conteudo_prof = f.read()
        assert "Gabarito" in conteudo_prof


def test_aluno_nao_contem_gabarito():
    """Arquivo do aluno não deve ter seção exclusiva do professor."""
    base = _base_minima()
    with tempfile.TemporaryDirectory() as pasta:
        resultados = _rodar_geracao(base, pasta)
        r = resultados[0]
        with open(r.caminho_aluno, "r", encoding="utf-8") as f:
            conteudo_aluno = f.read()
        # O gabarito específico não deve aparecer literalmente como seção no aluno
        assert "CADERNO_PROFESSOR" not in conteudo_aluno


def test_retomada_pula_par_completo():
    """Segunda execução sem --force deve pular disciplinas já geradas."""
    base = _base_minima()
    with tempfile.TemporaryDirectory() as pasta:
        # Primeira geração
        _rodar_geracao(base, pasta, force=False)

        # Segunda geração com contador
        contador = [0]
        def gerar_topico_spy(*a, **kw):
            contador[0] += 1
            return "ok"

        with (
            patch("src.output_formatter.markdown_generator.gerar_topico", gerar_topico_spy),
            patch("src.output_formatter.markdown_generator.gerar_questoes_topico",
                  lambda *a, **kw: ("qa", "qp")),
        ):
            resultados = gerar_markdowns(
                base_geral=base,
                buscar_chunks=_buscar_fake,
                gerar_documento=_gerar_doc_fake,
                model=_model_fake(),
                index=None,
                gemini=_client_fake(),
                pasta_saida=pasta,
                force=False,
                sleep_fn=lambda s: None,
            )

    assert contador[0] == 0, "Modo resume: gerar_topico não deve ser chamado no segundo run"
    assert resultados[0].pulada


def test_force_sobrescreve():
    """Com --force, disciplinas já geradas devem ser regeradas."""
    base = _base_minima()
    with tempfile.TemporaryDirectory() as pasta:
        # Primeira geração
        _rodar_geracao(base, pasta, force=False)

        contador = [0]
        def gerar_topico_spy(*a, **kw):
            contador[0] += 1
            return "Novo conteúdo sobrescrito"

        with (
            patch("src.output_formatter.markdown_generator.gerar_topico", gerar_topico_spy),
            patch("src.output_formatter.markdown_generator.gerar_questoes_topico",
                  lambda *a, **kw: ("qa_nova", "qp_nova")),
        ):
            gerar_markdowns(
                base_geral=base,
                buscar_chunks=_buscar_fake,
                gerar_documento=_gerar_doc_fake,
                model=_model_fake(),
                index=None,
                gemini=_client_fake(),
                pasta_saida=pasta,
                force=True,
                sleep_fn=lambda s: None,
            )

    assert contador[0] > 0, "Com --force, gerar_topico deve ser chamado novamente"


def test_area_ausente_retorna_erro():
    base = [{"arquivo": "x", "disciplina": "D1", "area": "", "ementa": "",
             "aula": 1, "titulo_aula": "T1", "conteudo": "c", "texto_embedding": "D1"}]
    with tempfile.TemporaryDirectory() as pasta:
        resultados = _rodar_geracao(base, pasta)
    assert resultados[0].erro != ""


def test_area_invalida_retorna_erro():
    base = [{"arquivo": "x", "disciplina": "D1", "area": "area_inexistente",
             "ementa": "", "aula": 1, "titulo_aula": "T1", "conteudo": "c",
             "texto_embedding": "D1"}]
    with tempfile.TemporaryDirectory() as pasta:
        resultados = _rodar_geracao(base, pasta)
    assert resultados[0].erro != ""


# ---------------------------------------------------------------------------
# juntar_topicos_formatado
# ---------------------------------------------------------------------------

def test_juntar_topicos_formatado_retorna_tuple():
    topicos = {"Tópico A": {"conteudo": "cont", "questoes_aluno": "qa", "questoes_professor": "qp"}}
    aluno, prof = juntar_topicos_formatado(
        "intro", "objetivos", topicos, "exemplos", "resumo", "q_aluno", "q_prof"
    )
    assert isinstance(aluno, str)
    assert isinstance(prof, str)


def test_juntar_topicos_aluno_sem_gabarito_professor():
    topicos = {"T1": {"conteudo": "x", "questoes_aluno": "pergunta", "questoes_professor": "GABARITO_SECRETO"}}
    aluno, prof = juntar_topicos_formatado("i", "o", topicos, "e", "r", "qa", "GABARITO_GERAL")
    assert "GABARITO_SECRETO" not in aluno
    assert "GABARITO_SECRETO" in prof


# ---------------------------------------------------------------------------
# texto_para_markdown
# ---------------------------------------------------------------------------

def test_texto_para_markdown_inclui_disciplina():
    md = texto_para_markdown("Minha Disciplina", "INTRODUCAO: Olá Mundo")
    assert "# Minha Disciplina" in md


def test_texto_para_markdown_inclui_secoes():
    md = texto_para_markdown("D", "INTRODUCAO: intro\nOBJETIVOS: obj")
    assert "## Introdução" in md
    assert "## Objetivos de Aprendizagem" in md
