import os
import json
from dotenv import load_dotenv

# EXTRAÇÃO
from src.pdf_csv.pdf_csv import extrair_pdf_para_csv
from src.syllabus_extractor.csv_processor import extrair_base_csv

# RAG
from src.content_generation.embedding_model import carregar_modelo, gerar_embeddings
from src.content_generation.faiss_index import criar_ou_carregar_index
from src.content_generation.rag_pipeline import buscar_chunks
from src.content_generation.generator import configurar_openai, gerar_documento

# OUTPUT
from src.output_formatter.markdown_generator import gerar_markdowns
from src.workbooks_generator.workbooks_generator import gerar_apostilas_por_curso
from src.video_generator.pipeline_video import gerar_videos_por_disciplina

load_dotenv()

# =========================
# PATHS
# =========================
PASTA_PDFS     = "data/input"
PASTA_CSV      = "data/input/planilhas_geradas"
PASTA_JSON     = "data/output/json"
PASTA_INDEX    = "data/output/faiss"
PASTA_MARKDOWN = "data/output/markdown"
PASTA_PDF      = "data/output/workbooks_pdf"
PASTA_VIDEO    = "data/output/videos"
LOGO_PATH      = "assets/logo.jpeg"

CAMINHO_JSON   = os.path.join(PASTA_JSON,  "base_geral.json")
CAMINHO_INDEX  = os.path.join(PASTA_INDEX, "faiss_index.bin")


# =========================
# MAIN
# =========================
def main():
    heyGen_token = os.getenv("HEYGEN_API_KEY")
    openai_token = os.getenv("OPENAI_API_KEY")

    # ------------------------------------------------------------------
    # 1. DESCOBRE TODOS OS PDFs em data/input/
    # ------------------------------------------------------------------
    
    pdfs = sorted([
        f for f in os.listdir(PASTA_PDFS)
        if f.lower().endswith(".pdf")
        and os.path.isfile(os.path.join(PASTA_PDFS, f))
    ])

    if not pdfs:
        print("❌ Nenhum PDF encontrado em data/input/. Adicione ao menos um PDF e tente novamente.")
        return

    print(f"\n📄 {len(pdfs)} PDF(s) encontrado(s):")
    for p in pdfs:
        print(f"   • {p}")

    os.makedirs(PASTA_CSV,   exist_ok=True)
    os.makedirs(PASTA_JSON,  exist_ok=True)
    os.makedirs(PASTA_INDEX, exist_ok=True)

    # ------------------------------------------------------------------
    # 2. PARA CADA PDF: extrai CSV → converte para JSON → acumula base
    # ------------------------------------------------------------------
    base_geral  = []
    pdfs_ok     = []

    for nome_pdf in pdfs:
        caminho_pdf = os.path.join(PASTA_PDFS, nome_pdf)

        print(f"\n{'='*60}")
        print(f"📄 Processando: {nome_pdf}")
        print(f"{'='*60}")

        # PDF → CSV
        nome_base   = nome_pdf.replace(".pdf", "")
        caminho_csv = os.path.join(PASTA_CSV, nome_base + ".csv")
        extrair_pdf_para_csv(caminho_pdf, caminho_csv)

        # CSV → JSON (por PDF) + acumula registros
        registros = extrair_base_csv(caminho_pdf, PASTA_CSV, PASTA_JSON)

        if not registros:
            print(f"   ⚠️  Nenhum registro extraído de {nome_pdf} — verifique se o PDF contém tabelas.")
            continue

        base_geral.extend(registros)
        pdfs_ok.append(nome_pdf)

        n_disc = len(set(r["disciplina"] for r in registros))
        print(f"   ✅ {n_disc} disciplina(s) | {len(registros)} tópico(s) extraídos")

    if not base_geral:
        print("\n❌ Base vazia após processar todos os PDFs. Encerrando.")
        return

    # ------------------------------------------------------------------
    # 3. SALVA base_geral.json CONSOLIDADA (todos os cursos / PDFs)
    # ------------------------------------------------------------------
    with open(CAMINHO_JSON, "w", encoding="utf-8") as f:
        json.dump(base_geral, f, ensure_ascii=False, indent=2)

    cursos_unicos = sorted(set(
        r.get("curso") or r.get("arquivo", "?") for r in base_geral
    ))
    print(f"\n✅ base_geral.json salvo:")
    print(f"   • {len(base_geral)} tópicos totais")
    print(f"   • {len(cursos_unicos)} curso(s): {cursos_unicos}")

    # ------------------------------------------------------------------
    # 4. EMBEDDINGS
    # ------------------------------------------------------------------
    print("\n🔢 Gerando embeddings...")
    model      = carregar_modelo()
    embeddings = gerar_embeddings(model, base_geral)

    # ------------------------------------------------------------------
    # 5. FAISS — reconstrói para garantir sincronia com a base atual
    # ------------------------------------------------------------------
    index = criar_ou_carregar_index(
        CAMINHO_INDEX,
        embeddings,
        forcar_rebuild=True,
    )

    # ------------------------------------------------------------------
    # 6. LLM
    # ------------------------------------------------------------------
    gemini = configurar_openai()

    # ------------------------------------------------------------------
    # 7. MARKDOWN — um .md por disciplina, uma pasta por curso
    # ------------------------------------------------------------------
    print("\n📝 Gerando markdowns...")
    gerar_markdowns(
        base_geral=base_geral,
        buscar_chunks=buscar_chunks,
        gerar_documento=gerar_documento,
        model=model,
        index=index,
        gemini=gemini,
        pasta_saida=PASTA_MARKDOWN,
    )
    
    # ------------------------------------------------------------------
    # 8. PDF — uma apostila por curso
    # ------------------------------------------------------------------
    print("\n📚 Gerando apostilas PDF...")
    gerar_apostilas_por_curso(
        pasta_markdown=PASTA_MARKDOWN,
        pasta_pdf=PASTA_PDF,
        logo_path=LOGO_PATH,
    )
    """
    # ------------------------------------------------------------------
    # 9. VÍDEOS — um vídeo por disciplina (requer HEYGEN_API_KEY)
    # ------------------------------------------------------------------
    if not heyGen_token:
        print("\n⚠️  HEYGEN_API_KEY não encontrada. Pulando geração de vídeos.")
    else:
        try:
            print("\n🎬 Gerando vídeos...")
            gerar_videos_por_disciplina(
                pasta_markdown=PASTA_MARKDOWN,
                pasta_saida=PASTA_VIDEO,
                openai_token=openai_token,
                heyGen_token=heyGen_token,
            )
        except Exception as e:
            print(f"❌ Erro na geração de vídeos: {e}")

    # ------------------------------------------------------------------
    # RESUMO FINAL
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"🎯 Pipeline finalizado!")
    print(f"   • {len(pdfs_ok)} PDF(s) processado(s): {pdfs_ok}")
    print(f"   • {len(cursos_unicos)} curso(s) gerado(s)")
    print(f"   • Markdowns  → {PASTA_MARKDOWN}")
    print(f"   • Apostilas  → {PASTA_PDF}")
    if heyGen_token:
        print(f"   • Vídeos     → {PASTA_VIDEO}")
    print(f"{'='*60}\n")
    """

# =========================
# ENTRYPOINT
# =========================
if __name__ == "__main__":
    main()
