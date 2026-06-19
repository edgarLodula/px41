"""Testes do parser de tópicos de células PDF."""

from src.pdf_csv.pdf_csv import normalizar_topicos_celula


def test_topico_unico():
    resultado = normalizar_topicos_celula("Anatomia humana")
    assert resultado == ["Anatomia humana"]


def test_continuacao_minuscula():
    texto = "História da oratória: da retórica\nclássica à comunicação moderna"
    resultado = normalizar_topicos_celula(texto)
    assert len(resultado) == 1
    assert "clássica" in resultado[0]
    assert "retórica" in resultado[0]


def test_continuacao_preposicao():
    texto = "Tom de voz, ritmo, volume e\nentonação"
    resultado = normalizar_topicos_celula(texto)
    assert len(resultado) == 1
    assert "entonação" in resultado[0]


def test_continuacao_planejamento():
    texto = "Planejamento e estruturação de\nfalas"
    resultado = normalizar_topicos_celula(texto)
    assert len(resultado) == 1
    assert "falas" in resultado[0]


def test_lista_com_bullets():
    texto = "- Tópico A\n- Tópico B\n- Tópico C"
    resultado = normalizar_topicos_celula(texto)
    assert len(resultado) == 3
    assert "Tópico A" in resultado[0]


def test_lista_numerada():
    texto = "1. Fundamentos\n2. Aplicações\n3. Avaliação"
    resultado = normalizar_topicos_celula(texto)
    assert len(resultado) == 3


def test_linhas_vazias_ignoradas():
    texto = "Tópico A\n\n\nTópico B"
    resultado = normalizar_topicos_celula(texto)
    # Sem marcadores explícitos, pode unir ou separar; não deve incluir vazio
    assert all(t.strip() for t in resultado)


def test_celula_vazia():
    assert normalizar_topicos_celula("") == []
    assert normalizar_topicos_celula("   ") == []
    assert normalizar_topicos_celula(None) == []  # type: ignore


def test_bullet_hifen():
    texto = "– Ponto um\n– Ponto dois"
    resultado = normalizar_topicos_celula(texto)
    assert len(resultado) == 2


def test_mantem_conteudo_original():
    texto = "- Higienização das mãos (5 momentos OMS)\n- 9 certos da medicação"
    resultado = normalizar_topicos_celula(texto)
    assert any("Higienização" in r for r in resultado)
    assert any("9 certos" in r for r in resultado)
