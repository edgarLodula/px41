def buscar_chunks(query, model, index, base_geral, top_k=5):
    q_emb = model.encode([query], normalize_embeddings=True).astype("float32")

    scores, indices = index.search(q_emb, top_k)

    resultados = []

    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue

        chunk = base_geral[idx].copy()
        chunk["score"] = float(score)
        resultados.append(chunk)

    return resultados