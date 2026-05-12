import os
import json
import pandas as pd
from dotenv import load_dotenv
# EXTRAÇÃO
from src.syllabus_extractor.pdf_processor import processar_pdf, processar_semantico
from src.syllabus_extractor.csv_processor import extrair_base_csv
from src.pdf_csv.pdf_csv import extrair_pdf_para_csv

load_dotenv()
# RAG
from src.content_generation.data_loader import carregar_base
from src.content_generation.embedding_model import carregar_modelo, gerar_embeddings
from src.content_generation.faiss_index import criar_ou_carregar_index
from src.content_generation.rag_pipeline import buscar_chunks
from src.content_generation.generator import configurar_gemini, gerar_documento

# OUTPUT
from src.output_formatter.markdown_generator import gerar_markdowns
from src.workbooks_generator.workbooks_generator import gerar_apostilas_por_curso
from src.video_generator.pipeline_video import gerar_videos_por_disciplina


# =========================
# PATHS
# =========================
PASTA_PDFS = "data/input/"
PASTA_JSON = "data/output/json"
PASTA_INDEX = "data/output/faiss"
PASTA_MARKDOWN = "data/output/markdown"
PASTA_PDF = "data/output/workbooks_pdf"
PASTA_VIDEO = "data/output/videos"
PASTA_CSV="data/input/planilhas_geradas"

LOGO_PATH = "assets/logo.jpeg"

CAMINHO_JSON = os.path.join(PASTA_JSON, "base_geral.json")
CAMINHO_INDEX = os.path.join(PASTA_INDEX, "faiss_index.bin")
CAMINHO_PDF="data/input/Tabela_Completa_Conteudo_Programatico_Tecnico_Enfermagem.docx.pdf"
gemini_token = os.getenv("GEMINI_API_KEY")

# =========================
# EXTRAÇÃO
# =========================
heyGen_token = os.getenv("HEYGEN_API_KEY")
gemini_token = os.getenv("GEMINI_API_KEY")
    

# =========================
# MAIN
# =========================
def main():
    # 1. EXTRAÇÃO
    nome_csv = os.path.basename(CAMINHO_PDF).replace(".pdf", ".csv")
    caminho_csv = os.path.join(PASTA_CSV, nome_csv)
    extrair_pdf_para_csv(CAMINHO_PDF, caminho_csv)
    extrair_base_csv(CAMINHO_PDF)

    # 2. BASE
    base_geral = carregar_base(CAMINHO_JSON)

    if not base_geral:
        print("❌ Base vazia. Encerrando.")
        return

    # 3. EMBEDDINGS
    model = carregar_modelo()
    embeddings = gerar_embeddings(model, base_geral)

    # 4. FAISS
    os.makedirs(PASTA_INDEX, exist_ok=True)
    index = criar_ou_carregar_index(CAMINHO_INDEX, embeddings)

    # 5. GEMINI
    gemini = configurar_gemini()

    # 6. MARKDOWN
    gerar_markdowns(
        base_geral=base_geral,
        buscar_chunks=buscar_chunks,
        gerar_documento=gerar_documento,
        model=model,
        index=index,
        gemini=gemini,
        pasta_saida=PASTA_MARKDOWN
    )

    # 7. PDF
    gerar_apostilas_por_curso(
        pasta_markdown=PASTA_MARKDOWN,
        pasta_pdf=PASTA_PDF,
        logo_path=LOGO_PATH
    )
    # 8. VIDEO
    

    if not heyGen_token:
        print("⚠️ Apis não encontradas. Pulando geração de vídeos.")
    else:
        try:
            gerar_videos_por_disciplina(
                pasta_markdown=PASTA_MARKDOWN,
                pasta_saida=PASTA_VIDEO,
                gemini_token=gemini_token,
                heyGen_token=heyGen_token
            )
        except Exception as e:
            print(f"❌ Erro na geração de vídeos: {e}")

    print("\n🎯 Pipeline finalizado!")
    

# =========================
# ENTRYPOINT
# =========================
if __name__ == "__main__":
    main()