"""Testes do pipeline RAG com filtro por área."""
import numpy as np
from unittest.mock import MagicMock

from src.content_generation.rag_pipeline import buscar_chunks


def _make_base(area: str, n: int = 3, nome_prefix: str = "disc") -> list[dict]:
    return [
        {
            "disciplina": f"{nome_prefix}_{i}",
            "conteudo": f"conteúdo {i}",
            "area": area,
            "curso": "curso_teste",
            "arquivo": f"{nome_prefix}.csv",
            "texto_embedding": f"{nome_prefix}_{i} conteúdo",
        }
        for i in range(n)
    ]


def _make_model_mock(dim: int = 4):
    """Modelo de embedding fake que gera vetores normalizados."""
    m = MagicMock()

    def encode(texts, normalize_embeddings=True):
        n = len(texts)
        vecs = np.random.rand(n, dim).astype("float32")
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.maximum(norms, 1e-9)

    m.encode.side_effect = encode
    return m


def _make_index_fake(base: list[dict], dim: int = 4):
    """Índice FAISS real (flat) criado em memória."""
    import faiss
    vecs = np.random.rand(len(base), dim).astype("float32")
    faiss.normalize_L2(vecs)
    idx = faiss.IndexFlatIP(dim)
    idx.add(vecs)
    return idx


class TestBuscarChunksSemFiltro:
    def test_retorna_top_k(self):
        base = _make_base("saude", 10)
        model = _make_model_mock()
        index = _make_index_fake(base)
        result = buscar_chunks("query", model, index, base, top_k=3)
        assert len(result) <= 3

    def test_retorna_lista_vazia_para_base_de_1(self):
        base = _make_base("saude", 1)
        model = _make_model_mock()
        index = _make_index_fake(base)
        result = buscar_chunks("query", model, index, base, top_k=5)
        assert len(result) >= 1  # ao menos 1 resultado

    def test_cada_resultado_tem_score(self):
        base = _make_base("saude", 5)
        model = _make_model_mock()
        index = _make_index_fake(base)
        result = buscar_chunks("query", model, index, base, top_k=3)
        for r in result:
            assert "score" in r


class TestBuscarChunksComFiltroArea:
    def test_filtra_area_correta(self):
        base_saude = _make_base("saude", 5, "saude")
        base_industrial = _make_base("industrial", 5, "industrial")
        base = base_saude + base_industrial

        model = _make_model_mock()
        index = _make_index_fake(base)

        result = buscar_chunks(
            "query", model, index, base, top_k=5, filtro_area="saude"
        )
        for r in result:
            assert r["area"] == "saude", (
                f"Esperava area='saude', recebi '{r['area']}'"
            )

    def test_nao_mistura_areas(self):
        base = _make_base("saude", 5, "saude") + _make_base("adm", 5, "adm")
        model = _make_model_mock()
        index = _make_index_fake(base)

        for area in ("saude", "adm"):
            result = buscar_chunks(
                "query", model, index, base, top_k=3, filtro_area=area
            )
            areas_retornadas = {r["area"] for r in result}
            assert areas_retornadas <= {area}, (
                f"Filtro '{area}' retornou áreas: {areas_retornadas}"
            )

    def test_filtro_sem_resultados_retorna_lista_vazia(self):
        base = _make_base("saude", 5)
        model = _make_model_mock()
        index = _make_index_fake(base)

        result = buscar_chunks(
            "query", model, index, base, top_k=3, filtro_area="area_inexistente"
        )
        assert result == []

    def test_ordenacao_por_score_preservada(self):
        base = _make_base("saude", 10)
        model = _make_model_mock()
        index = _make_index_fake(base)
        result = buscar_chunks(
            "query", model, index, base, top_k=5, filtro_area="saude"
        )
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True), (
            "Resultados devem estar ordenados por score decrescente"
        )
