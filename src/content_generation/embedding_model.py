from sentence_transformers import SentenceTransformer
import numpy as np


def carregar_modelo(nome_modelo: str = "paraphrase-multilingual-mpnet-base-v2"):
    print("🔄 Carregando modelo de embeddings...")
    model = SentenceTransformer(nome_modelo)
    print("✅ Modelo carregado")
    return model


def gerar_embeddings(model, base_geral: list):
    textos = [item["texto_embedding"] for item in base_geral]

    print(f"🔄 Gerando embeddings para {len(textos)} chunks...")

    embeddings = model.encode(
        textos,
        show_progress_bar=True,
        batch_size=32
    )

    embeddings = np.array(embeddings, dtype="float32")

    print(f"✅ Shape dos embeddings: {embeddings.shape}")

    return embeddings