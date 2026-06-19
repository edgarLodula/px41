"""
Pipeline RAG — busca de chunks semânticos com filtro opcional por área/curso/arquivo.

O FAISS não suporta filtro de metadata diretamente.
Estratégia: recuperar mais candidatos (oversampling) e filtrar por metadata Python-side.
"""
import logging

logger = logging.getLogger(__name__)

_MAX_CANDIDATOS = 100  # limite de segurança para o oversampling


def buscar_chunks(
    query: str,
    model,
    index,
    base_geral: list[dict],
    top_k: int = 5,
    filtro_area: str | None = None,
    filtro_curso: str | None = None,
    filtro_arquivo: str | None = None,
) -> list[dict]:
    """
    Busca os `top_k` chunks mais relevantes para a query.

    Parâmetros de filtro (opcionais, aplicados por metadata):
      - filtro_area    — retorna apenas chunks cuja chave 'area' bate (case-insensitive)
      - filtro_curso   — retorna apenas chunks do mesmo curso
      - filtro_arquivo — retorna apenas chunks do mesmo arquivo de origem

    Quando filtros estão ativos, recupera mais candidatos do índice e descarta
    os que não passam, garantindo retornar até `top_k` válidos.
    """
    usar_filtro = any(f is not None for f in (filtro_area, filtro_curso, filtro_arquivo))

    # Oversample para ter margem após filtrar
    n_candidatos = min(
        top_k * 10 if usar_filtro else top_k,
        max(index.ntotal, 1),
        _MAX_CANDIDATOS,
    )

    q_emb = model.encode([query], normalize_embeddings=True).astype("float32")
    scores, indices = index.search(q_emb, n_candidatos)

    resultados: list[dict] = []

    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(base_geral):
            continue

        chunk = base_geral[idx].copy()
        chunk["score"] = float(score)

        # Aplica filtros de metadata
        if filtro_area is not None:
            chunk_area = str(chunk.get("area", "")).strip().lower()
            if chunk_area != filtro_area.strip().lower():
                continue

        if filtro_curso is not None:
            chunk_curso = str(chunk.get("curso", "")).strip().lower()
            if chunk_curso != filtro_curso.strip().lower():
                continue

        if filtro_arquivo is not None:
            chunk_arquivo = str(chunk.get("arquivo", "")).strip().lower()
            if chunk_arquivo != filtro_arquivo.strip().lower():
                continue

        resultados.append(chunk)

        if len(resultados) >= top_k:
            break

    if usar_filtro and not resultados:
        logger.warning(
            "buscar_chunks: nenhum resultado após filtros "
            "(area=%r, curso=%r, arquivo=%r). "
            "Retornando lista vazia.",
            filtro_area, filtro_curso, filtro_arquivo,
        )

    return resultados
