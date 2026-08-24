"""
Pipeline principal de geração de apostilas técnicas.

Uso:
    python main.py [opções]

    --force              Sobrescreve arquivos existentes e força rebuild do índice.
    --rebuild-index      Força reconstrução do índice FAISS sem regenerar Markdown.
    --resume             Pula disciplinas já geradas (padrão quando --force não está ativo).
    --limit N            Processa no máximo N disciplinas (útil para smoke tests).
    --validate-only      Valida imports, dependências e profiles sem chamar a API.
    --skip-pdf           Pula a conversão de Markdown para PDF.
    --log-level LEVEL    DEBUG | INFO | WARNING | ERROR (padrão: INFO).
"""
import os
import sys
import json
import glob
import logging
import argparse
import traceback

from dotenv import load_dotenv
from src.pdf_csv.pdf_csv import extrair_pdf_para_csv
from src.syllabus_extractor.csv_processor import extrair_base_csv
from src.pdf_csv.pdf_csv import aplicar_correcoes
from src.content_generation.embedding_model import carregar_modelo, gerar_embeddings
from src.content_generation.faiss_index import criar_ou_carregar_index
from src.content_generation.rag_pipeline import buscar_chunks
from src.content_generation.generator import configurar_openai, gerar_documento
from src.content_generation.area_profiles import get_profile
from src.content_generation.area_detector import detectar_area_do_input
from src.output_formatter.markdown_generator import gerar_markdowns
from src.workbooks_generator.workbooks_generator import gerar_apostilas_por_curso

# ---------------------------------------------------------------------------
# CAMINHOS PADRÃO
# ---------------------------------------------------------------------------
PASTA_PDFS = "data/input"
PASTA_CSV = "data/input/planilhas_geradas"
PASTA_JSON = "data/output/json"
PASTA_INDEX = "data/output/faiss"
PASTA_MARKDOWN = "data/output/markdown"
PASTA_PDF = "data/output/workbooks_pdf"
LOGO_PATH = "assets/logo.jpeg"

CAMINHO_JSON = os.path.join(PASTA_JSON, "base_geral.json")
CAMINHO_INDEX = os.path.join(PASTA_INDEX, "faiss_index.bin")

# Mapeamento manual opcional: nome_base_do_pdf → area_key
# Deixe vazio para usar apenas detecção automática.
AREA_POR_PDF: dict[str, str] = {
    "Tabela_Completa_Conteudo_Programatico_Tecnico_Enfermagem": "tecnico_enfermagem",
    "Tabela_Conteudo_Programatico_Tecnico_Administracao": "tecnico_administracao",
    "Tabela_Conteudo_Programatico_Tecnico_Eletromecanica": "tecnico_eletromecanica",
    "Tabela_Conteudo_Programatico_Tecnico_Eletrotecnica": "tecnico_eletrotecnica",
    "Tabela_Conteudo_Programatico_Tecnico_Refrigeracao_Climatizacao": "refrigeracao_climatizacao",
    "Técnico em Oratória - Ementa e Conteúdo Programático (1)": "curso_oratoria",
    "Técnico em Segurança do Trabalho - Ementa e Conteúdo Programático":"curso_seguranca_no_trabalho",
    "Técnico em Logística - Ementa e Conteúdo Programático (1)":"curso_logistica",

}


# ---------------------------------------------------------------------------
# DETECÇÃO DE ÁREA
# ---------------------------------------------------------------------------

def _resolver_area_pdf(
    caminho_pdf: str,
    nome_pdf: str,
    client=None,
) -> tuple[str, str]:
    """
    Retorna (area_key, estrategia_usada).

    Ordem de prioridade:
      1. Override manual em AREA_POR_PDF.
      2. Detecção automática pelo CONTEÚDO (título → heurística → LLM).
    """
    base = nome_pdf.replace(".pdf", "")

    if base in AREA_POR_PDF:
        area_key = AREA_POR_PDF[base]
        get_profile(area_key)  # valida imediatamente; lança ValueError se inválida
        return area_key, "override_manual"

    det = detectar_area_do_input(caminho_pdf, client=client)
    return det["area_key"], det["estrategia"]


# ---------------------------------------------------------------------------
# ARGPARSE
# ---------------------------------------------------------------------------

def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pipeline de geração de apostilas técnicas com RAG + OpenAI"
    )
    p.add_argument("--force", action="store_true",
                   help="Sobrescreve arquivos existentes e força rebuild do índice FAISS")
    p.add_argument("--rebuild-index", action="store_true",
                   help="Força reconstrução do índice FAISS")
    p.add_argument("--resume", action="store_true", default=True,
                   help="Pula disciplinas já geradas (padrão)")
    p.add_argument("--limit", type=int, default=0, metavar="N",
                   help="Processa no máximo N disciplinas (0 = sem limite)")
    p.add_argument("--validate-only", action="store_true",
                   help="Valida imports, profiles e dependências sem chamar API")
    p.add_argument("--skip-pdf", action="store_true",
                   help="Pula a conversão final de Markdown para PDF")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                   help="Nível de logging (padrão: INFO)")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# VALIDATE-ONLY
# ---------------------------------------------------------------------------

def _validar_ambiente() -> bool:
    """Valida imports, profiles e dependências. Retorna True se tudo OK."""
    ok = True

    print("\n=== VALIDATE-ONLY ===")

    # Profiles
    try:
        from src.content_generation.area_profiles import AREA_PROFILES, get_profile
        print(f"  ✅ AREA_PROFILES: {len(AREA_PROFILES)} profiles carregados")
        for k in AREA_PROFILES:
            get_profile(k)
        print("  ✅ Todos os profiles validados")
    except Exception as exc:
        print(f"  ❌ Falha nos profiles: {exc}")
        ok = False

    # Detector
    try:
        print("  ✅ area_detector importado")
    except Exception as exc:
        print(f"  ❌ area_detector: {exc}")
        ok = False

    # Generator
    try:
        print("  ✅ generator importado")
    except Exception as exc:
        print(f"  ❌ generator: {exc}")
        ok = False

    # Markdown generator
    try:
        print("  ✅ markdown_generator importado")
    except Exception as exc:
        print(f"  ❌ markdown_generator: {exc}")
        ok = False

    # FAISS
    try:
        import faiss
        print(f"  ✅ faiss importado (versão: {faiss.__version__})")
    except Exception as exc:
        print(f"  ❌ faiss: {exc}")
        ok = False

    # Dependências opcionais
    for dep in ("pdfplumber", "pdfkit", "pytesseract"):
        try:
            __import__(dep)
            print(f"  ✅ {dep} importado")
        except ImportError:
            print(f"  ⚠️  {dep} não instalado (opcional)")

    # Diretórios de entrada
    if os.path.isdir(PASTA_PDFS):
        pdfs = [f for f in os.listdir(PASTA_PDFS) if f.lower().endswith(".pdf")]
        print(f"  ✅ {PASTA_PDFS}: {len(pdfs)} PDFs encontrados")
    else:
        print(f"  ⚠️  Diretório de entrada '{PASTA_PDFS}' não existe")

    print("=== FIM VALIDATE-ONLY ===\n")
    return ok


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    load_dotenv()
    args = _parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.validate_only:
        return 0 if _validar_ambiente() else 1

    heyGen_token = os.getenv("HEYGEN_API_KEY")

    # ---- Inicializa client OpenAI antes do loop de PDFs ----
    # O client é necessário para a detecção por LLM (fallback).
    # Se a chave não estiver disponível, client=None e o LLM não é usado na detecção.
    client = None
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            client = configurar_openai()
        except Exception as exc:
            logging.warning("Não foi possível inicializar OpenAI: %s", exc)
    else:
        logging.warning(
            "OPENAI_API_KEY não encontrada. Detecção por LLM desativada; "
            "geração de conteúdo falhará se necessária."
        )

    # ---- Descobre PDFs ----
    if not os.path.isdir(PASTA_PDFS):
        print(f"Diretório de entrada não encontrado: '{PASTA_PDFS}'")
        return 1

    pdfs = sorted(
        f for f in os.listdir(PASTA_PDFS)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(PASTA_PDFS, f))
    )

    if not pdfs:
        print(
            f"Nenhum PDF encontrado em '{PASTA_PDFS}'. "
            "Adicione ao menos um PDF e tente novamente."
        )
        return 1

    print(f"\n{len(pdfs)} PDF(s) encontrado(s):")
    for p in pdfs:
        print(f"   • {p}")

    os.makedirs(PASTA_CSV, exist_ok=True)
    os.makedirs(PASTA_JSON, exist_ok=True)
    os.makedirs(PASTA_INDEX, exist_ok=True)

    # ---- Processa cada PDF ----
    base_geral: list[dict] = []
    pdfs_ok: list[str] = []
    pdfs_ignorados: list[str] = []
    areas_detectadas: dict[str, str] = {}
    erros_pdf: list[str] = []

    for nome_pdf in pdfs:
        caminho_pdf = os.path.join(PASTA_PDFS, nome_pdf)

        print(f"\n{'='*60}")
        print(f"Processando: {nome_pdf}")
        print(f"{'='*60}")

        try:
            area_pdf, estrategia = _resolver_area_pdf(caminho_pdf, nome_pdf, client)
            profile_pdf = get_profile(area_pdf)
            print(
                f"   Área detectada: {profile_pdf['nome_area']} "
                f"({profile_pdf['nome_profissional']}) [via {estrategia}]"
            )
        except ValueError as exc:
            msg = f"Área não detectada em '{nome_pdf}': {exc}"
            logging.error(msg)
            print(f"   ❌ {msg} — pulando este PDF.")
            erros_pdf.append(msg)
            pdfs_ignorados.append(nome_pdf)
            continue
        except Exception as exc:
            msg = f"Erro inesperado ao detectar área de '{nome_pdf}': {exc}"
            logging.error("%s\n%s", msg, traceback.format_exc())
            print(f"   ❌ {msg}")
            erros_pdf.append(msg)
            pdfs_ignorados.append(nome_pdf)
            continue

        areas_detectadas[nome_pdf] = area_pdf

        # PDF → CSV
        nome_base = nome_pdf.replace(".pdf", "")
        caminho_csv = os.path.join(PASTA_CSV, nome_base + ".csv")
        try:
                extrair_pdf_para_csv(caminho_pdf, caminho_csv)
        except Exception as exc:
                msg = f"Erro ao extrair CSV de '{nome_pdf}': {exc}"
                logging.error(msg)
                print(f"   ❌ {msg}")
                erros_pdf.append(msg)
                pdfs_ignorados.append(nome_pdf)
                continue

            # 📝 Aplica correções automáticas (ementas truncadas, tópicos faltantes)
        n_corrigidas = aplicar_correcoes(caminho_csv)
        if n_corrigidas:
                print(f"   📝 {n_corrigidas} linha(s) complementada(s) via correcoes_csv.json")

            # CSV → registros
        try:
                registros = extrair_base_csv(caminho_pdf, PASTA_CSV, PASTA_JSON)
        except Exception as exc:
            msg = f"Erro ao processar CSV de '{nome_pdf}': {exc}"
            logging.error(msg)
            print(f"   ❌ {msg}")
            erros_pdf.append(msg)
            pdfs_ignorados.append(nome_pdf)
            continue

        if not registros:
            print(f"   Nenhum registro extraído de '{nome_pdf}'.")
            pdfs_ignorados.append(nome_pdf)
            continue

        # Injeta área em cada registro
        for r in registros:
            r["area"] = area_pdf

        base_geral.extend(registros)
        pdfs_ok.append(nome_pdf)

        n_disc = len({r["disciplina"] for r in registros})
        print(f"   {n_disc} disciplina(s) | {len(registros)} tópico(s) extraídos")

    if not base_geral:
        print("\nBase vazia após processar todos os PDFs. Encerrando.")
        return 1

    # ---- Salva base_geral.json ----
    with open(CAMINHO_JSON, "w", encoding="utf-8") as f:
        json.dump(base_geral, f, ensure_ascii=False, indent=2)

    cursos_unicos = sorted({r.get("curso") or r.get("arquivo", "?") for r in base_geral})
    print(f"\nbase_geral.json salvo: {len(base_geral)} tópicos | {len(cursos_unicos)} curso(s)")

    # ---- Limita disciplinas se --limit ----
    if args.limit > 0:
        disc_set: set[str] = set()
        base_limitada: list[dict] = []
        for r in base_geral:
            key = f"{r.get('arquivo','')}/{r.get('disciplina','')}"
            if key not in disc_set:
                if len(disc_set) >= args.limit:
                    break
                disc_set.add(key)
            base_limitada.append(r)
        base_geral = base_limitada
        print(f"   (--limit {args.limit}: {len(disc_set)} disciplinas selecionadas)")

    # ---- Embeddings ----
    print("\nGerando embeddings...")
    try:
        model = carregar_modelo()
        embeddings = gerar_embeddings(model, base_geral)
    except Exception as exc:
        logging.critical("Falha ao gerar embeddings: %s\n%s", exc, traceback.format_exc())
        print(f"❌ Falha crítica nos embeddings: {exc}")
        return 1

    # ---- FAISS ----
    forcar_rebuild = args.force or args.rebuild_index
    try:
        index = criar_ou_carregar_index(
            CAMINHO_INDEX,
            embeddings,
            forcar_rebuild=forcar_rebuild,
            n_registros=len(base_geral),
        )
    except Exception as exc:
        logging.critical("Falha ao criar/carregar índice FAISS: %s\n%s",
                         exc, traceback.format_exc())
        print(f"❌ Falha crítica no FAISS: {exc}")
        return 1

    # ---- Verifica client para geração de conteúdo ----
    if client is None:
        print("\n❌ OPENAI_API_KEY não configurada. Não é possível gerar conteúdo.")
        return 1

    # ---- Gera Markdowns ----
    print("\nGerando Markdowns...")
    try:
        resultados = gerar_markdowns(
            base_geral=base_geral,
            buscar_chunks=buscar_chunks,
            gerar_documento=gerar_documento,
            model=model,
            index=index,
            gemini=client,
            pasta_saida=PASTA_MARKDOWN,
            force=args.force,
        )
    except (TypeError, NameError, AttributeError) as exc:
        logging.critical("Bug de programação em gerar_markdowns: %s\n%s",
                         exc, traceback.format_exc())
        print(f"🐛 BUG crítico em gerar_markdowns: {exc}")
        return 1
    except Exception as exc:
        logging.critical("Falha crítica em gerar_markdowns: %s\n%s",
                         exc, traceback.format_exc())
        print(f"❌ Falha crítica em gerar_markdowns: {exc}")
        return 1

    # ---- Gera PDFs ----
    n_aluno = 0
    n_prof = 0
    if not args.skip_pdf:
        print("\nGerando apostilas PDF...")
        try:
            gerar_apostilas_por_curso(
                pasta_markdown=PASTA_MARKDOWN,
                pasta_pdf=PASTA_PDF,
                logo_path=LOGO_PATH,
            )
        except Exception as exc:
            logging.error("Falha na geração de PDFs: %s", exc)
            print(f"⚠️  Falha na geração de PDFs (Markdowns preservados): {exc}")

        n_aluno = len(glob.glob(os.path.join(PASTA_PDF, "aluno", "*", "*.pdf")))
        n_prof = len(glob.glob(os.path.join(PASTA_PDF, "professor", "*", "*.pdf")))
    else:
        print("\n(--skip-pdf: conversão para PDF pulada)")

    # ---- Resumo final ----
    gerados = sum(1 for r in resultados if r.caminho_aluno and not r.pulada and not r.erro)
    puladas = sum(1 for r in resultados if r.pulada)
    erros_md = sum(1 for r in resultados if r.erro)
    houve_falha = bool(erros_pdf) or erros_md > 0

    print(f"\n{'='*60}")
    if houve_falha:
        print("Pipeline concluído COM ERROS")
    else:
        print("Pipeline finalizado com sucesso!")
    print(f"  PDFs encontrados      : {len(pdfs)}")
    print(f"  PDFs processados      : {len(pdfs_ok)}")
    print(f"  PDFs ignorados        : {len(pdfs_ignorados)}")
    print(f"  Áreas detectadas      : {dict(areas_detectadas)}")
    print(f"  Disciplinas geradas   : {gerados}")
    print(f"  Disciplinas puladas   : {puladas}")
    print(f"  Erros de disciplina   : {erros_md}")
    print(f"  Erros de PDF          : {len(erros_pdf)}")
    print(f"  Markdowns (aluno)     : {PASTA_MARKDOWN}")
    print(f"  Markdowns (professor) : {PASTA_MARKDOWN}")
    if not args.skip_pdf:
        print(f"  PDFs aluno            : {n_aluno}")
        print(f"  PDFs professor        : {n_prof}")
        print(f"  Apostilas             : {PASTA_PDF}/{{aluno|professor}}/<curso>/<disciplina>.pdf")
    if heyGen_token:
        print("  Vídeos                : configurado mas desabilitado nesta execução")
    if erros_pdf:
        print("\nErros de PDF:")
        for e in erros_pdf:
            print(f"   • {e}")
    print(f"{'='*60}\n")

    return 1 if houve_falha else 0


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
