"""
Gerenciamento do índice FAISS com metadata/fingerprint para detecção de incompatibilidade.

Um arquivo <caminho_index>.meta.json acompanha o índice e armazena:
  - n_vetores: quantidade de vetores indexados
  - dim: dimensão dos embeddings
  - modelo: nome do modelo de embedding
  - criado_em: timestamp ISO
"""
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone

import faiss
import numpy as np

logger = logging.getLogger(__name__)

_MODELO_PADRAO = "paraphrase-multilingual-mpnet-base-v2"


def _caminho_meta(caminho_index: str) -> str:
    return caminho_index + ".meta.json"


def _ler_meta(caminho_index: str) -> dict | None:
    meta_path = _caminho_meta(caminho_index)
    if not os.path.isfile(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Falha ao ler metadata do índice: %s", exc)
        return None


def _salvar_meta(caminho_index: str, n_vetores: int, dim: int, modelo: str) -> None:
    meta = {
        "n_vetores": n_vetores,
        "dim": dim,
        "modelo": modelo,
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = _caminho_meta(caminho_index)
    dir_destino = os.path.dirname(meta_path) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_destino, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, meta_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _indice_compativel(
    caminho_index: str,
    n_esperado: int,
    dim_esperado: int,
) -> bool:
    """
    Verifica se o índice salvo é compatível com a base atual.
    Retorna False se incompatível (deve reconstruir).
    """
    if not os.path.isfile(caminho_index):
        return False

    meta = _ler_meta(caminho_index)
    if meta is None:
        logger.warning(
            "Índice existente sem metadata — será reconstruído para garantir integridade."
        )
        return False

    if meta.get("n_vetores") != n_esperado:
        logger.warning(
            "Índice incompatível: %d vetores salvos vs %d esperados. Reconstruindo.",
            meta["n_vetores"], n_esperado,
        )
        return False

    if meta.get("dim") != dim_esperado:
        logger.warning(
            "Índice incompatível: dimensão %d salva vs %d esperada. Reconstruindo.",
            meta["dim"], dim_esperado,
        )
        return False

    return True


def criar_ou_carregar_index(
    caminho_index: str,
    embeddings: np.ndarray,
    forcar_rebuild: bool = False,
    n_registros: int | None = None,
    modelo: str = _MODELO_PADRAO,
) -> faiss.Index:
    """
    Cria ou carrega um índice FAISS IndexFlatIP.

    Parâmetros:
      caminho_index  — caminho do arquivo .bin do índice
      embeddings     — array numpy float32 shape (n, dim)
      forcar_rebuild — ignora índice existente e reconstrói
      n_registros    — número de registros na base atual (para validação)
      modelo         — nome do modelo de embedding (para metadata)

    Usa serialize/deserialize + Python file I/O para suportar caminhos Unicode no Windows.
    """
    n_esperado = n_registros if n_registros is not None else len(embeddings)
    dim_esperado = embeddings.shape[1]

    pode_carregar = (
        not forcar_rebuild
        and _indice_compativel(caminho_index, n_esperado, dim_esperado)
    )

    if pode_carregar:
        logger.info("Carregando índice FAISS do disco: %s", caminho_index)
        print("📂 Carregando índice FAISS do disco...")
        try:
            with open(caminho_index, "rb") as f:
                data = np.frombuffer(f.read(), dtype="uint8")
            index = faiss.deserialize_index(data)
            print(f"✅ Índice carregado: {index.ntotal} vetores")
            return index
        except Exception as exc:
            logger.warning(
                "Falha ao carregar índice existente: %s — reconstruindo.", exc
            )

    # Reconstrução
    razao = "forçado pelo usuário" if forcar_rebuild else "incompatibilidade ou ausência"
    print(f"🔄 Criando/recriando índice FAISS ({razao})...")

    emb = np.ascontiguousarray(embeddings, dtype="float32")
    faiss.normalize_L2(emb)

    index = faiss.IndexFlatIP(dim_esperado)
    index.add(emb)

    # Salva atomicamente
    os.makedirs(os.path.dirname(caminho_index) or ".", exist_ok=True)
    dir_destino = os.path.dirname(caminho_index) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_destino, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            data = faiss.serialize_index(index)
            f.write(data.tobytes())
        shutil.move(tmp_path, caminho_index)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    _salvar_meta(caminho_index, index.ntotal, dim_esperado, modelo)
    print(f"✅ Índice criado e salvo: {index.ntotal} vetores (dim={dim_esperado})")
    return index
