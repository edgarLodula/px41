"""Testes dos profiles de área e aliases."""
import copy
import pytest

from src.content_generation.area_profiles import (
    AREA_PROFILES,
    _ALIASES,
    _REQUIRED_KEYS,
    get_profile,
)


# ---------------------------------------------------------------------------
# Chaves obrigatórias
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("area_key", list(AREA_PROFILES.keys()))
def test_profile_tem_chaves_obrigatorias(area_key):
    profile = AREA_PROFILES[area_key]
    ausentes = _REQUIRED_KEYS - set(profile.keys())
    assert not ausentes, (
        f"Profile '{area_key}' está faltando: {sorted(ausentes)}"
    )


@pytest.mark.parametrize("area_key", list(AREA_PROFILES.keys()))
def test_profile_tipos_de_lista(area_key):
    profile = AREA_PROFILES[area_key]
    for campo in ("ambientes_de_trabalho", "equipamentos_tipicos",
                  "normas_regulamentadoras", "normas_tecnicas",
                  "vocabulario_proibido", "regras_terminologia_obrigatorias",
                  "referencias_oficiais_obrigatorias"):
        assert isinstance(profile[campo], list), (
            f"Profile '{area_key}': campo '{campo}' deveria ser list, "
            f"é {type(profile[campo])}"
        )


@pytest.mark.parametrize("area_key", list(AREA_PROFILES.keys()))
def test_profile_tipos_de_string(area_key):
    profile = AREA_PROFILES[area_key]
    for campo in ("nome_area", "nome_profissional", "grandezas_tipicas",
                  "tecnologias_emergentes", "softwares_tipicos",
                  "epis_tipicos", "procedimentos_seguranca_chave"):
        assert isinstance(profile[campo], str), (
            f"Profile '{area_key}': campo '{campo}' deveria ser str"
        )


# ---------------------------------------------------------------------------
# get_profile — casos válidos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("area_key", list(AREA_PROFILES.keys()))
def test_get_profile_chave_canonica(area_key):
    p = get_profile(area_key)
    assert isinstance(p, dict)
    assert p["nome_area"]


@pytest.mark.parametrize("alias, esperado", list(_ALIASES.items()))
def test_get_profile_alias(alias, esperado):
    p = get_profile(alias)
    assert p["nome_area"] == AREA_PROFILES[esperado]["nome_area"]


def test_get_profile_retorna_copia():
    p1 = get_profile("tecnico_enfermagem")
    p2 = get_profile("tecnico_enfermagem")
    p1["nome_area"] = "MODIFICADO"
    assert p2["nome_area"] != "MODIFICADO", (
        "get_profile deve retornar cópia; modificar uma não deve afetar a outra"
    )


def test_get_profile_nao_modifica_global():
    original = copy.deepcopy(AREA_PROFILES["tecnico_enfermagem"])
    p = get_profile("tecnico_enfermagem")
    p["novo_campo"] = "INJETADO"
    assert "novo_campo" not in AREA_PROFILES["tecnico_enfermagem"]
    assert AREA_PROFILES["tecnico_enfermagem"] == original


# ---------------------------------------------------------------------------
# get_profile — casos inválidos
# ---------------------------------------------------------------------------

def test_get_profile_area_invalida_lanca_erro():
    with pytest.raises(ValueError, match="não encontrada"):
        get_profile("area_inexistente_xyz")


def test_get_profile_vazio_lanca_erro():
    with pytest.raises(ValueError):
        get_profile("")


def test_get_profile_none_lanca_erro():
    with pytest.raises((ValueError, AttributeError)):
        get_profile(None)  # type: ignore


# ---------------------------------------------------------------------------
# Profiles diferentes são diferentes
# ---------------------------------------------------------------------------

def test_profiles_distintos():
    enf = get_profile("tecnico_enfermagem")
    adm = get_profile("tecnico_administracao")
    assert enf["nome_area"] != adm["nome_area"]
    assert enf["vocabulario_proibido"] != adm["vocabulario_proibido"]


def test_vocabulario_proibido_nao_contem_termos_da_area():
    for area_key, profile in AREA_PROFILES.items():
        nome_area_low = profile["nome_area"].lower()
        for termo in profile.get("vocabulario_proibido", []):
            # Um profile não deve proibir seu próprio nome de área
            assert nome_area_low not in termo.lower() or len(nome_area_low) < 4, (
                f"Profile '{area_key}' proíbe termo '{termo}' que contém seu próprio nome"
            )


# ---------------------------------------------------------------------------
# Oratória — testes de contaminação
# ---------------------------------------------------------------------------

def test_oratoria_tem_vocabulario_proibido():
    """Oratória deve banir termos de Administração."""
    p = get_profile("curso_oratoria")
    proibidos_low = [t.lower() for t in p["vocabulario_proibido"]]
    for termo_adm in ("ERP", "SAP", "CRA", "KPI", "ROI"):
        assert termo_adm.lower() in proibidos_low, (
            f"Oratória deveria proibir '{termo_adm}', mas não proíbe. "
            f"Lista atual: {p['vocabulario_proibido']}"
        )


def test_oratoria_nao_usa_ambiente_administrativo():
    """Ambientes de trabalho de oratória não devem ser de escritório corporativo genérico."""
    p = get_profile("curso_oratoria")
    ambientes_low = " ".join(p["ambientes_de_trabalho"]).lower()
    # Ambientes oratória: palco, câmera, podcast, auditório...
    assert "palco" in ambientes_low or "auditório" in ambientes_low.replace("ó", "o")
    # Não deve ter ambientes industriais
    for termo in ("chão de fábrica", "subestação", "uti"):
        assert termo not in ambientes_low, (
            f"Ambiente '{termo}' não deveria estar no profile de oratória"
        )


def test_oratoria_tem_referencias_bibliograficas():
    """Oratória deve incluir referências específicas da área."""
    p = get_profile("curso_oratoria")
    refs_texto = " ".join(p.get("referencias_oficiais_obrigatorias", []))
    for autor in ("Carnegie", "Cialdini", "Polito"):
        assert autor in refs_texto, (
            f"Referência de '{autor}' ausente no profile de oratória"
        )


def test_oratoria_alias_reconhecido():
    """Aliases 'oratoria' e 'oratória' devem resolver para curso_oratoria."""
    from src.content_generation.area_profiles import _ALIASES
    for alias in ("oratoria", "oratória", "comunicacao oral"):
        chave = _ALIASES.get(alias)
        assert chave == "curso_oratoria", (
            f"Alias '{alias}' resolve para '{chave}', esperava 'curso_oratoria'"
        )


def test_oratoria_sem_nome_profissional_administracao():
    """Profile de oratória não deve chamar o profissional de 'técnico em administração'."""
    p = get_profile("curso_oratoria")
    assert "administração" not in p["nome_profissional"].lower()
    assert "técnico em" not in p["nome_profissional"].lower()
