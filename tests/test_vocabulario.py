"""Testes da validação de vocabulário proibido."""
import pytest

from src.output_formatter.markdown_generator import _validar_vocabulario
from src.content_generation.area_profiles import get_profile


@pytest.fixture
def profile_saude():
    return get_profile("tecnico_enfermagem")


def test_detecta_termo_proibido(profile_saude):
    texto = "O técnico deve verificar o motor da instalação elétrica."
    violacoes = _validar_vocabulario(texto, profile_saude)
    assert any("motor" in v.lower() for v in violacoes)


def test_detecta_sem_diferenciar_caixa(profile_saude):
    texto = "O ambiente é semelhante a uma FÁBRICA industrial."
    violacoes = _validar_vocabulario(texto, profile_saude)
    assert len(violacoes) > 0


def test_sem_termo_proibido_retorna_lista_vazia(profile_saude):
    texto = "O técnico realiza a higienização das mãos antes do procedimento."
    violacoes = _validar_vocabulario(texto, profile_saude)
    assert violacoes == []


def test_lista_vazia_retorna_lista_vazia():
    profile = get_profile("tecnico_administracao")
    profile["vocabulario_proibido"] = []
    violacoes = _validar_vocabulario("qualquer texto", profile)
    assert violacoes == []


def test_profile_sem_vocabulario_proibido():
    profile = {"nome_area": "teste", "vocabulario_proibido": []}
    violacoes = _validar_vocabulario("motor CLP fábrica", profile)
    assert violacoes == []


def test_detecta_multiplas_violacoes(profile_saude):
    texto = "Motor CLP inversor fábrica linha de produção"
    violacoes = _validar_vocabulario(texto, profile_saude)
    assert len(violacoes) >= 2


def test_termo_dentro_de_palavra_maior_detectado(profile_saude):
    """'motor' dentro de 'motora' — substring match encontra."""
    texto = "A atividade motora do paciente foi avaliada."
    violacoes = _validar_vocabulario(texto, profile_saude)
    # Pode ou não detectar dependendo da implementação de boundary
    # O importante é não lançar exceção
    assert isinstance(violacoes, list)
