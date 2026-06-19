"""Testes do índice FAISS com metadata/fingerprint."""
import numpy as np
import os
import pytest
import tempfile

from src.content_generation.faiss_index import (
    criar_ou_carregar_index,
    _ler_meta,
    _indice_compativel,
)


def _rand_emb(n: int, dim: int = 8) -> np.ndarray:
    vecs = np.random.rand(n, dim).astype("float32")
    return vecs


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def test_cria_indice_e_salva_metadata(tmp_dir):
    path = os.path.join(tmp_dir, "test.bin")
    emb = _rand_emb(10)
    index = criar_ou_carregar_index(path, emb)
    assert index.ntotal == 10
    assert os.path.isfile(path)
    meta = _ler_meta(path)
    assert meta is not None
    assert meta["n_vetores"] == 10
    assert meta["dim"] == 8


def test_carrega_indice_existente_compativel(tmp_dir):
    path = os.path.join(tmp_dir, "test.bin")
    emb = _rand_emb(5, 8)
    criar_ou_carregar_index(path, emb, n_registros=5)
    # Segunda chamada: deve carregar sem reconstruir
    index2 = criar_ou_carregar_index(path, emb, n_registros=5)
    assert index2.ntotal == 5


def test_reconstroi_quando_n_vetores_diverge(tmp_dir):
    path = os.path.join(tmp_dir, "test.bin")
    emb5 = _rand_emb(5, 8)
    criar_ou_carregar_index(path, emb5, n_registros=5)
    # Agora com 10 registros — deve reconstruir
    emb10 = _rand_emb(10, 8)
    index = criar_ou_carregar_index(path, emb10, n_registros=10)
    assert index.ntotal == 10


def test_reconstroi_quando_dim_diverge(tmp_dir):
    path = os.path.join(tmp_dir, "test.bin")
    emb_dim8 = _rand_emb(5, 8)
    criar_ou_carregar_index(path, emb_dim8, n_registros=5)
    # Agora com dimensão diferente — deve reconstruir
    emb_dim16 = _rand_emb(5, 16)
    index = criar_ou_carregar_index(path, emb_dim16, n_registros=5)
    assert index.d == 16


def test_force_rebuild(tmp_dir):
    path = os.path.join(tmp_dir, "test.bin")
    emb = _rand_emb(5, 8)
    criar_ou_carregar_index(path, emb, n_registros=5)
    # Force rebuild mesmo com mesma configuração
    index = criar_ou_carregar_index(path, emb, forcar_rebuild=True, n_registros=5)
    assert index.ntotal == 5


def test_indice_sem_metadata_reconstroi(tmp_dir):
    path = os.path.join(tmp_dir, "test.bin")
    emb = _rand_emb(5, 8)
    # Cria índice manualmente sem metadata
    import faiss
    idx = faiss.IndexFlatIP(8)
    idx.add(emb)
    data = faiss.serialize_index(idx)
    with open(path, "wb") as f:
        f.write(data.tobytes())
    # Sem metadata → incompatível → deve reconstruir
    assert not _indice_compativel(path, 5, 8)
