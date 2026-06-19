"""
Testa que as funções de geração recebem e usam o profile correto.
Nunca chama a API real.
"""
import pytest
from unittest.mock import MagicMock, patch

from src.content_generation.area_profiles import get_profile
from src.content_generation.generator import (
    gerar_topico,
    gerar_questoes_topico,
    gerar_documento,
    _bloco_contexto_area,
    _bloco_regras,
    _validar_profile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def profile_enfermagem():
    return get_profile("tecnico_enfermagem")


@pytest.fixture
def profile_administracao():
    return get_profile("tecnico_administracao")


@pytest.fixture
def client_fake():
    """Client OpenAI falso que retorna texto determinístico."""
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="Conteúdo gerado pelo LLM fake para o tópico solicitado."
        ))]
    )
    return client


# ---------------------------------------------------------------------------
# _validar_profile
# ---------------------------------------------------------------------------

def test_validar_profile_valido(profile_enfermagem):
    _validar_profile(profile_enfermagem, "teste")  # não deve lançar


def test_validar_profile_invalido_lanca_erro():
    with pytest.raises(ValueError):
        _validar_profile({}, "teste")


def test_validar_profile_none_lanca_erro():
    with pytest.raises(ValueError):
        _validar_profile(None, "teste")


# ---------------------------------------------------------------------------
# _bloco_contexto_area
# ---------------------------------------------------------------------------

def test_bloco_contexto_usa_area_correta(profile_enfermagem):
    ctx = _bloco_contexto_area(profile_enfermagem)
    assert "saúde" in ctx.lower()
    assert "técnico em enfermagem" in ctx.lower()


def test_bloco_contexto_diferentes_para_diferentes_profiles(
    profile_enfermagem, profile_administracao
):
    ctx_enf = _bloco_contexto_area(profile_enfermagem)
    ctx_adm = _bloco_contexto_area(profile_administracao)
    assert ctx_enf != ctx_adm


def test_bloco_regras_industrial_nao_aparece_em_enfermagem(profile_enfermagem):
    regras = _bloco_regras(profile_enfermagem)
    assert "engenharia industrial" not in regras.lower()


# ---------------------------------------------------------------------------
# gerar_topico — usa o profile passado, não env var
# ---------------------------------------------------------------------------

def test_gerar_topico_usa_profile_correto(client_fake, profile_enfermagem):
    with patch("src.content_generation.generator._chamar_api") as mock_api:
        mock_api.return_value = "Conteúdo fake do tópico"
        resultado = gerar_topico(
            client_fake, "Anatomia", "Sistemas do corpo", "contexto", profile_enfermagem
        )
    assert resultado == "Conteúdo fake do tópico"
    # O prompt enviado deve mencionar a área correta
    prompt_enviado = mock_api.call_args[0][1]
    assert "saúde" in prompt_enviado.lower() or "enfermagem" in prompt_enviado.lower()


def test_gerar_topico_profile_industrial_nao_aparece_em_enfermagem(
    client_fake, profile_enfermagem
):
    with patch("src.content_generation.generator._chamar_api") as mock_api:
        mock_api.return_value = "ok"
        gerar_topico(
            client_fake, "Sinais Vitais", "PA, FC, FR", "ctx", profile_enfermagem
        )
    prompt = mock_api.call_args[0][1]
    # Prompt não deve mencionar "industrial" como área desta apostila
    assert "apostila de industrial" not in prompt.lower()
    assert "apostila de eletromecânica" not in prompt.lower()


# ---------------------------------------------------------------------------
# gerar_questoes_topico — retorna tupla (aluno, professor)
# ---------------------------------------------------------------------------

def test_gerar_questoes_topico_retorna_tupla(client_fake, profile_enfermagem):
    with patch("src.content_generation.generator._chamar_api") as mock_api:
        mock_api.return_value = (
            "Questão 1\n===CADERNO_PROFESSOR===\nGabarito 1"
        )
        aluno, prof = gerar_questoes_topico(
            client_fake, "Anatomia", "Sistemas", "ctx", profile_enfermagem
        )
    assert isinstance(aluno, str)
    assert isinstance(prof, str)
    assert "Questão" in aluno
    assert "Gabarito" in prof


def test_gerar_questoes_topico_usa_profile(client_fake, profile_enfermagem):
    with patch("src.content_generation.generator._chamar_api") as mock_api:
        mock_api.return_value = "Questões\n===CADERNO_PROFESSOR===\nGabarito"
        gerar_questoes_topico(
            client_fake, "Farmacologia", "Medicamentos", "ctx", profile_enfermagem
        )
    prompt = mock_api.call_args[0][1]
    assert "saúde" in prompt.lower() or "enfermagem" in prompt.lower()


# ---------------------------------------------------------------------------
# gerar_documento — repassa o profile
# ---------------------------------------------------------------------------

def test_gerar_documento_introducao(client_fake, profile_administracao):
    with patch("src.content_generation.generator._chamar_api") as mock_api:
        mock_api.return_value = "Introdução gerada"
        resultado = gerar_documento(
            client_fake,
            "Gestão Financeira",
            "Fluxo de caixa",
            "Gere apenas a introdução.",
            "ctx",
            profile_administracao,
        )
    assert "Introdução" in resultado
    prompt = mock_api.call_args[0][1]
    assert "administração" in prompt.lower()


def test_gerar_documento_questoes_retorna_tupla(client_fake, profile_administracao):
    with patch("src.content_generation.generator._chamar_api") as mock_api:
        mock_api.return_value = "Q1\n===CADERNO_PROFESSOR===\nGab1"
        resultado = gerar_documento(
            client_fake,
            "Gestão Financeira",
            "Fluxo de caixa",
            "Gere a avaliação geral completa da disciplina com questões.",
            "ctx",
            profile_administracao,
        )
    assert isinstance(resultado, tuple)


def test_gerar_documento_profile_invalido(client_fake):
    with pytest.raises(ValueError):
        gerar_documento(client_fake, "D", "E", "intro", "ctx", {})


# ---------------------------------------------------------------------------
# Routing de gerar_documento — questões antes de exemplos
# ---------------------------------------------------------------------------

def test_gerar_documento_casos_praticos_roteia_para_questoes(client_fake, profile_administracao):
    """
    A instrução padrão de questões contém 'casos práticos'.
    Deve rotear para _gerar_questoes, não _gerar_exemplos.
    """
    instrucao = (
        "Gere a avaliação geral completa da disciplina com questões "
        "objetivas, dissertativas e baseadas em casos práticos."
    )
    chamadas_questoes = []
    chamadas_exemplos = []

    def questoes_spy(client, disciplina, ementa, contexto, profile):
        chamadas_questoes.append(1)
        return "questoes_aluno", "questoes_professor"

    def exemplos_spy(client, disciplina, ementa, contexto, profile):
        chamadas_exemplos.append(1)
        return "exemplos gerados"

    with (
        patch("src.content_generation.generator._gerar_questoes", questoes_spy),
        patch("src.content_generation.generator._gerar_exemplos", exemplos_spy),
    ):
        gerar_documento(client_fake, "D", "E", instrucao, "ctx", profile_administracao)

    assert len(chamadas_questoes) == 1, (
        "Instrução com 'casos práticos' + 'avaliação' deve chamar _gerar_questoes"
    )
    assert len(chamadas_exemplos) == 0, (
        "_gerar_exemplos não deve ser chamado quando a instrução é de avaliação"
    )


def test_gerar_documento_exemplos_praticos_roteia_para_exemplos(client_fake, profile_administracao):
    """A instrução 'Gere apenas exemplos práticos.' deve chamar _gerar_exemplos."""
    chamadas_exemplos = []

    def exemplos_spy(client, disciplina, ementa, contexto, profile):
        chamadas_exemplos.append(1)
        return "exemplos"

    with patch("src.content_generation.generator._gerar_exemplos", exemplos_spy):
        gerar_documento(client_fake, "D", "E", "Gere apenas exemplos práticos.", "ctx",
                        profile_administracao)

    assert len(chamadas_exemplos) == 1


# ---------------------------------------------------------------------------
# Nenhuma função consulta AREA_FORMACAO
# ---------------------------------------------------------------------------

def test_sem_dependencia_de_area_formacao(monkeypatch, profile_enfermagem, client_fake):
    """Remove a variável AREA_FORMACAO do ambiente — nada deve quebrar."""
    monkeypatch.delenv("AREA_FORMACAO", raising=False)
    with patch("src.content_generation.generator._chamar_api", return_value="ok"):
        resultado = gerar_topico(
            client_fake, "Disciplina", "Tópico", "ctx", profile_enfermagem
        )
    assert resultado == "ok"
