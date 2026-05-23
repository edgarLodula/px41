import os
import faiss
import numpy as np


def criar_ou_carregar_index(caminho_index, embeddings, forcar_rebuild: bool = False):
    """
    Cria ou carrega um índice FAISS IndexFlatIP.

    Usa serialize/deserialize + Python file I/O para evitar o bug do fopen do C++
    que não consegue abrir caminhos Windows com caracteres acentuados (ex: Á, É).
    """
    if not forcar_rebuild and os.path.exists(caminho_index):
        print("📂 Carregando índice FAISS do disco...")
        with open(caminho_index, "rb") as f:
            data = np.frombuffer(f.read(), dtype="uint8")
        index = faiss.deserialize_index(data)
        print(f"✅ Índice carregado: {index.ntotal} vetores")
    else:
        if forcar_rebuild:
            print("🔄 Recriando índice FAISS...")
        else:
            print("🔄 Criando novo índice FAISS...")

        # normalize_L2 modifica in-place: garante float32 C-contíguo antes
        embeddings = np.ascontiguousarray(embeddings, dtype="float32")
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        # Serializa via Python para suportar caminhos Unicode no Windows
        data = faiss.serialize_index(index)
        with open(caminho_index, "wb") as f:
            f.write(data.tobytes())

        print(f"✅ Índice criado e salvo: {index.ntotal} vetores (dim={dim})")

    return index
