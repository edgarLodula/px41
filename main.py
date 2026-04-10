import os
import json

# EXTRAÇÃO
from src.syllabus_extractor.pdf_processor import processar_pdf, processar_semantico

# RAG
from src.content_generation.data_loader import carregar_base
from src.content_generation.embedding_model import carregar_modelo, gerar_embeddings
from src.content_generation.faiss_index import criar_ou_carregar_index
from src.content_generation.rag_pipeline import buscar_chunks
from src.content_generation.generator import configurar_gemini, gerar_documento

# OUTPUT
from src.output_formatter.markdown_generator import gerar_markdowns


# -------------------------
# PATHS
# -------------------------
PASTA_PDFS = "data/input"
PASTA_JSON = "data/output/json"
PASTA_INDEX = "data/output/faiss"

CAMINHO_JSON = os.path.join(PASTA_JSON, "base_geral.json")
CAMINHO_INDEX = os.path.join(PASTA_INDEX, "faiss_index.bin")


def extrair_base():
    os.makedirs(PASTA_JSON, exist_ok=True)

    arquivos_pdf = [f for f in os.listdir(PASTA_PDFS) if f.endswith(".pdf")]

    base_geral = []

    for arquivo in arquivos_pdf:
        caminho_pdf = os.path.join(PASTA_PDFS, arquivo)

        print(f"\n📄 Processando PDF: {arquivo}")

        paginas = processar_pdf(caminho_pdf)
        base_ia = processar_semantico(paginas, arquivo)

        base_geral.extend(base_ia)

    with open(CAMINHO_JSON, "w", encoding="utf-8") as f:
        json.dump(base_geral, f, ensure_ascii=False, indent=2)

    print(f"\n✅ JSON salvo em: {CAMINHO_JSON}")


def main():
    # -------------------------
    # 1. EXTRAÇÃO PDF → JSON
    # -------------------------
    extrair_base()

    # -------------------------
    # 2. CARREGA BASE
    # -------------------------
    base_geral = carregar_base(CAMINHO_JSON)

    # -------------------------
    # 3. EMBEDDINGS
    # -------------------------
    model = carregar_modelo()
    embeddings = gerar_embeddings(model, base_geral)

    # -------------------------
    # 4. FAISS
    # -------------------------
    os.makedirs(PASTA_INDEX, exist_ok=True)
    index = criar_ou_carregar_index(CAMINHO_INDEX, embeddings)

    # -------------------------
    # 5. GEMINI
    # -------------------------
    gemini = configurar_gemini()

    # -------------------------
    # 6. GERA MARKDOWNS
    # -------------------------
    gerar_markdowns(
        base_geral=base_geral,
        buscar_chunks=buscar_chunks,
        gerar_documento=gerar_documento,
        model=model,
        index=index,
        gemini=gemini
    )


if __name__ == "__main__":
    main()