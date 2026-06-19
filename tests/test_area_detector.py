"""Testes da detecção automática de área."""
import pytest
from unittest.mock import MagicMock
import tempfile
import os

from src.content_generation.area_detector import (
    _detectar_por_titulo,
    _detectar_por_conteudo_heuristico,
    _detectar_por_llm,
    detectar_area_do_input,
)
from src.content_generation.area_profiles import AREA_PROFILES


# ---------------------------------------------------------------------------
# _detectar_por_titulo
# ---------------------------------------------------------------------------

def test_titulo_detecta_enfermagem():
    texto = "CURSO TÉCNICO EM ENFERMAGEM\nConteúdo Programático"
    resultado = _detectar_por_titulo(texto)
    assert resultado == "tecnico_enfermagem"


def test_titulo_detecta_administracao():
    texto = "Técnico em Administração\nGrade Curricular"
    resultado = _detectar_por_titulo(texto)
    assert resultado == "tecnico_administracao"


def test_titulo_detecta_eletrotecnica():
    texto = "CURSO TÉCNICO DE ELETROTÉCNICA\nDisciplinas"
    resultado = _detectar_por_titulo(texto)
    assert resultado == "tecnico_eletrotecnica"


def test_titulo_retorna_none_para_texto_generico():
    texto = "Documento sem informação de curso"
    resultado = _detectar_por_titulo(texto)
    assert resultado is None or resultado in AREA_PROFILES


# ---------------------------------------------------------------------------
# _detectar_por_conteudo_heuristico
# ---------------------------------------------------------------------------

def test_heuristica_saude():
    texto = (
        "esfigmomanômetro estetoscópio oxímetro monitor bomba infusão "
        "enfermaria UTI pronto-socorro centro cirúrgico home care "
        "glicosímetro termômetro sinais vitais"
    )
    resultado = _detectar_por_conteudo_heuristico(texto)
    assert resultado == "tecnico_enfermagem"


def test_heuristica_retorna_none_sem_termos():
    texto = "texto sem termos técnicos relevantes"
    resultado = _detectar_por_conteudo_heuristico(texto)
    assert resultado is None


# ---------------------------------------------------------------------------
# _detectar_por_llm (mock)
# ---------------------------------------------------------------------------

def test_llm_retorna_chave_valida():
    client_mock = MagicMock()
    client_mock.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="  tecnico_enfermagem  "))]
    )
    resultado = _detectar_por_llm(client_mock, "apostila de saúde")
    assert resultado == "tecnico_enfermagem"


def test_llm_retorna_none_para_resposta_invalida():
    client_mock = MagicMock()
    client_mock.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="area_inexistente"))]
    )
    resultado = _detectar_por_llm(client_mock, "texto qualquer")
    assert resultado is None


# ---------------------------------------------------------------------------
# detectar_area_do_input
# ---------------------------------------------------------------------------

def test_override_manual():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("conteúdo irrelevante")
        tmp = f.name
    try:
        resultado = detectar_area_do_input(tmp, override="tecnico_administracao")
        assert resultado["area_key"] == "tecnico_administracao"
        assert resultado["estrategia"] == "override"
    finally:
        os.unlink(tmp)


def test_arquivo_vazio_lanca_erro():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("")
        tmp = f.name
    try:
        with pytest.raises(ValueError, match="vazio"):
            detectar_area_do_input(tmp)
    finally:
        os.unlink(tmp)


def test_arquivo_inexistente_lanca_erro():
    with pytest.raises(FileNotFoundError):
        detectar_area_do_input("/caminho/inexistente/arquivo.pdf")


def test_deteccao_por_titulo_via_txt():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            "CURSO TÉCNICO EM ENFERMAGEM\n"
            "esfigmomanômetro estetoscópio oxímetro\n"
        )
        tmp = f.name
    try:
        resultado = detectar_area_do_input(tmp)
        assert resultado["area_key"] == "tecnico_enfermagem"
        assert resultado["estrategia"] in ("titulo", "heuristica", "llm")
    finally:
        os.unlink(tmp)
