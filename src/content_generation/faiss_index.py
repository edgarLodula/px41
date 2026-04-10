import os
import faiss
import numpy as np


def criar_ou_carregar_index(caminho_index, embeddings):
    if os.path.exists(caminho_index):
        print("📂 Carregando índice FAISS do disco...")
        index = faiss.read_index(caminho_index)
        print(f"✅ Índice carregado: {index.ntotal} vetores")
    else:
        print("🔄 Criando novo índice FAISS...")

        faiss.normalize_L2(embeddings)

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        faiss.write_index(index, caminho_index)

        print(f"✅ Índice criado e salvo: {index.ntotal} vetores")

    return index