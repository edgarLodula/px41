import os
import re
import json
import threading
import tempfile
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# =========================
# IMPORTS DO PIPELINE
# =========================
from src.syllabus_extractor.pdf_processor import processar_pdf, processar_semantico
from src.content_generation.data_loader import carregar_base
from src.content_generation.embedding_model import carregar_modelo, gerar_embeddings
from src.content_generation.faiss_index import criar_ou_carregar_index
from src.content_generation.rag_pipeline import buscar_chunks
from src.content_generation.generator import configurar_gemini, gerar_documento
from src.output_formatter.markdown_generator import gerar_markdowns
from src.workbooks_generator.workbooks_generator import gerar_apostilas_por_curso
from src.video_generator.pipeline_video import gerar_videos_por_disciplina
from src.video_generator.gerador_videos_direto import (
    novo_job,
    extrair_markdown_do_pdf,
    gerar_roteiro,
    parsear_cenas_do_roteiro,
    gerar_video_heygen,
    aguardar_video,
    verificar_status_video,
    extrair_falas_do_roteiro,
    LIMITE_DISCIPLINAS,
    LIMITE_PALAVRAS,
)

# =========================
# PATHS
# =========================
PASTA_PDFS     = "data/input"
PASTA_JSON     = "data/output/json"
PASTA_INDEX    = "data/output/faiss"
PASTA_MARKDOWN = "data/output/markdown"
PASTA_PDF      = "data/output/workbooks_pdf"
PASTA_VIDEO    = "data/output/videos"
ARQUIVO_ROTEIROS = "data/output/roteiros.json"
ARQUIVO_CENAS    = "data/output/cenas.json"
LOGO_PATH      = "assets/logo.jpeg"
CAMINHO_JSON   = os.path.join(PASTA_JSON, "base_geral.json")
CAMINHO_INDEX  = os.path.join(PASTA_INDEX, "faiss_index.bin")

from dotenv import load_dotenv
load_dotenv()

# =========================
# ESTADO GLOBAL DO PIPELINE
# =========================
pipeline_state = {
    "stage": 0,
    "status": "idle",
    # Possíveis status do pipeline principal:
    # idle | running | awaiting_discipline_selection |
    # awaiting_approval | generating_scripts |
    # awaiting_scripts_approval | awaiting_scenes_approval |
    # generating_video | done | error
    "stages": [
        {"name": "Extração de PDFs",     "status": "waiting"},
        {"name": "Carregamento da base", "status": "waiting"},
        {"name": "Embeddings",           "status": "waiting"},
        {"name": "Índice FAISS",         "status": "waiting"},
        {"name": "Configuração Gemini",  "status": "waiting"},
        {"name": "Geração de Markdown",  "status": "waiting"},
        {"name": "Apostila PDF",         "status": "waiting"},
        {"name": "Geração de Vídeo",     "status": "waiting"},
    ],
    "error": None,
    "apostila_path": None,
    "video_path": None,
    "video_paths": {},
    "scripts": {},
    "scenes":  [],
    # Seleção de disciplinas
    "all_disciplines":      [],   # todas encontradas no PDF
    "selected_disciplines": [],   # selecionadas pelo usuário para gerar conteúdo
    "current_discipline":   None, # disciplina sendo processada agora (fase 3)
    "total_disciplines":    0,
    "done_disciplines":     0,
    # Estado intermediário do pipeline (para retomar após seleção)
    "_pipeline_ctx": {},
}

def set_stage(index, status):
    pipeline_state["stage"] = index
    pipeline_state["stages"][index]["status"] = status

def reset_state():
    pipeline_state["stage"] = 0
    pipeline_state["status"] = "idle"
    pipeline_state["error"] = None
    pipeline_state["apostila_path"] = None
    pipeline_state["video_path"] = None
    pipeline_state["video_paths"] = {}
    pipeline_state["scripts"] = {}
    pipeline_state["scenes"]  = []
    pipeline_state["all_disciplines"]      = []
    pipeline_state["selected_disciplines"] = []
    pipeline_state["current_discipline"]   = None
    pipeline_state["total_disciplines"]    = 0
    pipeline_state["done_disciplines"]     = 0
    pipeline_state["_pipeline_ctx"]        = {}
    for s in pipeline_state["stages"]:
        s["status"] = "waiting"

# =========================
# PIPELINE EM THREAD
# =========================
def run_pipeline():
    try:
        os.makedirs(PASTA_JSON, exist_ok=True)
        os.makedirs(PASTA_INDEX, exist_ok=True)

        # ── Stage 0: Extração ────────────────────────────────────────────────
        set_stage(0, "running")
        pipeline_state["status"] = "running"
        arquivos_pdf = [f for f in os.listdir(PASTA_PDFS) if f.endswith(".pdf")]
        base_geral = []
        for arquivo in arquivos_pdf:
            caminho_pdf = os.path.join(PASTA_PDFS, arquivo)
            paginas = processar_pdf(caminho_pdf)
            base_ia = processar_semantico(paginas, arquivo)
            base_geral.extend(base_ia)
        with open(CAMINHO_JSON, "w", encoding="utf-8") as f:
            json.dump(base_geral, f, ensure_ascii=False, indent=2)
        set_stage(0, "done")

        # ── Stage 1: Carregar base ───────────────────────────────────────────
        set_stage(1, "running")
        base_geral = carregar_base(CAMINHO_JSON)
        if not base_geral:
            raise Exception("Base vazia após extração.")
        set_stage(1, "done")

        # ── Stage 2: Embeddings ──────────────────────────────────────────────
        set_stage(2, "running")
        model = carregar_modelo()
        embeddings = gerar_embeddings(model, base_geral)
        set_stage(2, "done")

        # ── Stage 3: Índice FAISS ────────────────────────────────────────────
        set_stage(3, "running")
        index = criar_ou_carregar_index(CAMINHO_INDEX, embeddings)
        set_stage(3, "done")

        # ── Stage 4: Configurar Gemini ───────────────────────────────────────
        set_stage(4, "running")
        gemini = configurar_gemini()
        set_stage(4, "done")

        # ── Pausa: seleção de disciplinas ────────────────────────────────────
        # Extrai lista de disciplinas únicas para o usuário escolher
        disciplinas_unicas = sorted({
            item.get("disciplina", "").strip()
            for item in base_geral
            if item.get("disciplina", "").strip()
        })
        pipeline_state["all_disciplines"]  = disciplinas_unicas
        pipeline_state["_pipeline_ctx"]    = {
            "base_geral": base_geral,
            "model":      model,
            "index":      index,
            "gemini":     gemini,
        }
        pipeline_state["status"] = "awaiting_discipline_selection"
        # Pipeline pausa aqui — continua via POST /select-disciplines

    except Exception as e:
        pipeline_state["status"] = "error"
        pipeline_state["error"] = str(e)
        for s in pipeline_state["stages"]:
            if s["status"] == "running":
                s["status"] = "error"


def run_pipeline_content(disciplinas_selecionadas: list[str]):
    """
    Continua o pipeline (stages 5–7) apenas com as disciplinas selecionadas.
    Chamado após o usuário confirmar a seleção.
    """
    try:
        ctx        = pipeline_state["_pipeline_ctx"]
        base_geral = ctx["base_geral"]
        model      = ctx["model"]
        index      = ctx["index"]
        gemini     = ctx["gemini"]

        # Filtra base para as disciplinas selecionadas
        if disciplinas_selecionadas:
            base_filtrada = [
                item for item in base_geral
                if item.get("disciplina", "").strip() in disciplinas_selecionadas
            ]
        else:
            base_filtrada = base_geral

        pipeline_state["status"]           = "running"
        pipeline_state["selected_disciplines"] = disciplinas_selecionadas
        pipeline_state["total_disciplines"]    = len({
            i.get("disciplina") for i in base_filtrada
        })

        def _on_disciplina(nome: str, concluidas: int, total: int):
            pipeline_state["current_discipline"] = nome
            pipeline_state["done_disciplines"]   = concluidas
            pipeline_state["total_disciplines"]  = total

        # ── Stage 5: Geração de Markdown ────────────────────────────────────
        set_stage(5, "running")
        gerar_markdowns(
            base_geral=base_filtrada,
            buscar_chunks=buscar_chunks,
            gerar_documento=gerar_documento,
            model=model,
            index=index,
            gemini=gemini,
            pasta_saida=PASTA_MARKDOWN,
            on_disciplina=_on_disciplina,
            base_rag=base_geral,   # usa a base COMPLETA para o RAG — evita index out of range
        )
        pipeline_state["current_discipline"] = None
        set_stage(5, "done")

        # ── Stage 6: Apostila PDF (não-fatal: continua mesmo sem wkhtmltopdf) ──
        set_stage(6, "running")
        try:
            gerar_apostilas_por_curso(
                pasta_markdown=PASTA_MARKDOWN,
                pasta_pdf=PASTA_PDF,
                logo_path=LOGO_PATH
            )
            set_stage(6, "done")
            pdfs = [f for f in os.listdir(PASTA_PDF) if f.endswith(".pdf")]
            if pdfs:
                pipeline_state["apostila_path"] = os.path.join(PASTA_PDF, pdfs[0])
        except Exception as e_apostila:
            # Apostila falhou (ex: wkhtmltopdf não instalado) — apenas avisa e continua
            set_stage(6, "error")
            pipeline_state["error"] = f"Apostila: {e_apostila} (pipeline continua)"
            print(f"AVISO - Apostila nao gerada: {e_apostila}")

        pipeline_state["status"] = "awaiting_approval"

    except Exception as e:
        pipeline_state["status"] = "error"
        pipeline_state["error"] = str(e)
        for s in pipeline_state["stages"]:
            if s["status"] == "running":
                s["status"] = "error"


def run_video():
    """
    Etapa 7 (nova): gera roteiros de produção a partir dos markdowns gerados
    e aguarda aprovação do usuário antes de chamar o HeyGen.
    """
    try:
        set_stage(7, "running")
        gemini_token = os.getenv("GEMINI_API_KEY")
        if not gemini_token:
            raise Exception("GEMINI_API_KEY não configurada.")

        pipeline_state["status"] = "generating_scripts"

        # Lê todos os markdowns gerados e cria um roteiro por disciplina
        scripts = {}
        for curso in os.listdir(PASTA_MARKDOWN):
            caminho_curso = os.path.join(PASTA_MARKDOWN, curso)
            if not os.path.isdir(caminho_curso):
                continue
            for arquivo in os.listdir(caminho_curso):
                if not arquivo.endswith(".md"):
                    continue
                disciplina = arquivo.replace(".md", "").replace("_", " ")
                caminho_md = os.path.join(caminho_curso, arquivo)
                with open(caminho_md, "r", encoding="utf-8") as f:
                    markdown_text = f.read()

                print(f"Gerando roteiro: {disciplina}")
                roteiro = gerar_roteiro(markdown_text, disciplina, gemini_token)
                chave = f"{curso}|{arquivo.replace('.md', '')}"
                scripts[chave] = {
                    "nome":        disciplina,
                    "curso":       curso,
                    "arquivo_md":  caminho_md,
                    "roteiro":     roteiro,
                }
                import time as _time
                _time.sleep(2)  # evita rate limit

        pipeline_state["scripts"] = scripts
        pipeline_state["status"]  = "awaiting_scripts_approval"
        set_stage(7, "done")

        # Persiste roteiros em disco para retomada futura
        os.makedirs("data/output", exist_ok=True)
        with open(ARQUIVO_ROTEIROS, "w", encoding="utf-8") as f:
            json.dump(scripts, f, ensure_ascii=False, indent=2)

    except Exception as e:
        pipeline_state["status"] = "error"
        pipeline_state["error"]  = str(e)
        set_stage(7, "error")


def run_heygen_videos(cenas_aprovadas: list):
    """Gera vídeos HeyGen para as disciplinas aprovadas."""
    try:
        pipeline_state["status"] = "generating_video"
        heygen_token = os.getenv("HEYGEN_API_KEY")
        if not heygen_token:
            raise Exception("HEYGEN_API_KEY não configurada.")

        falas = extrair_falas_do_roteiro(cenas_aprovadas)
        if not falas:
            raise Exception("Nenhuma fala encontrada nas cenas aprovadas.")

        video_paths: dict[str, str] = {}
        os.makedirs(PASTA_VIDEO, exist_ok=True)

        for disciplina, fala in falas.items():
            print(f"Gerando video: {disciplina}")
            video_id = gerar_video_heygen(fala, disciplina, heygen_token)
            info     = aguardar_video(video_id, heygen_token)

            if info.get("video_url"):
                import requests as req
                slug   = re.sub(r"[^\w]", "_", disciplina)[:60]
                caminho = os.path.join(PASTA_VIDEO, f"{slug}.mp4")
                video_bytes = req.get(info["video_url"], timeout=60).content
                with open(caminho, "wb") as f:
                    f.write(video_bytes)
                video_paths[disciplina] = caminho

        pipeline_state["video_paths"] = video_paths
        pipeline_state["video_path"]  = list(video_paths.values())[0] if video_paths else None
        pipeline_state["status"]      = "done"

    except Exception as e:
        pipeline_state["status"] = "error"
        pipeline_state["error"]  = str(e)


# =========================
# APP FASTAPI
# =========================
app = FastAPI(title="ATRIA San Marino API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/check-existing")
def check_existing():
    """
    Verifica se existem artefatos gerados em sessões anteriores.
    Retorna o que está disponível para retomar o pipeline.
    """
    resultado = {
        "tem_markdown":    False,
        "tem_apostila":    False,
        "tem_base_json":   False,
        "tem_roteiros":    False,
        "tem_cenas":       False,
        "disciplinas_md":  [],
        "cursos_md":       [],
        "apostilas":       [],
        "num_roteiros":    0,
        "num_cenas":       0,
    }

    if os.path.exists(CAMINHO_JSON):
        resultado["tem_base_json"] = True

    if os.path.exists(PASTA_MARKDOWN):
        for curso in os.listdir(PASTA_MARKDOWN):
            caminho_curso = os.path.join(PASTA_MARKDOWN, curso)
            if not os.path.isdir(caminho_curso):
                continue
            arquivos_md = [f.replace(".md", "").replace("_", " ")
                           for f in os.listdir(caminho_curso) if f.endswith(".md")]
            if arquivos_md:
                resultado["tem_markdown"] = True
                resultado["cursos_md"].append(curso)
                resultado["disciplinas_md"].extend(arquivos_md)

    if os.path.exists(PASTA_PDF):
        pdfs = [f for f in os.listdir(PASTA_PDF) if f.endswith(".pdf")]
        if pdfs:
            resultado["tem_apostila"] = True
            resultado["apostilas"] = pdfs

    if os.path.exists(ARQUIVO_ROTEIROS):
        try:
            with open(ARQUIVO_ROTEIROS, encoding="utf-8") as f:
                roteiros = json.load(f)
            resultado["tem_roteiros"] = bool(roteiros)
            resultado["num_roteiros"] = len(roteiros)
        except Exception:
            pass

    if os.path.exists(ARQUIVO_CENAS):
        try:
            with open(ARQUIVO_CENAS, encoding="utf-8") as f:
                cenas = json.load(f)
            resultado["tem_cenas"] = bool(cenas)
            resultado["num_cenas"] = len(cenas)
        except Exception:
            pass

    return resultado


@app.post("/retomar-de-roteiros")
def retomar_de_roteiros():
    """Retoma o pipeline carregando os roteiros salvos em disco."""
    if not os.path.exists(ARQUIVO_ROTEIROS):
        return JSONResponse(status_code=400, content={"error": "Arquivo de roteiros não encontrado."})

    with open(ARQUIVO_ROTEIROS, encoding="utf-8") as f:
        scripts = json.load(f)

    reset_state()
    for i in range(7):
        set_stage(i, "done")
    pipeline_state["scripts"] = scripts
    pipeline_state["status"]  = "awaiting_scripts_approval"
    return {"message": f"{len(scripts)} roteiro(s) carregado(s). Pronto para revisão."}


@app.post("/retomar-de-cenas")
def retomar_de_cenas():
    """Retoma o pipeline carregando as cenas salvas em disco — útil quando o HeyGen falha."""
    if not os.path.exists(ARQUIVO_CENAS):
        return JSONResponse(status_code=400, content={"error": "Arquivo de cenas não encontrado."})

    with open(ARQUIVO_CENAS, encoding="utf-8") as f:
        cenas = json.load(f)

    reset_state()
    for i in range(7):
        set_stage(i, "done")
    pipeline_state["scenes"] = cenas
    pipeline_state["status"] = "awaiting_scenes_approval"
    return {"message": f"{len(cenas)} disciplina(s) com cenas carregadas. Pronto para gerar vídeos."}


@app.post("/retomar-de-markdown")
def retomar_de_markdown():
    """
    Retoma o pipeline a partir dos markdowns já gerados.
    Pula extração de PDF, embeddings, RAG e geração de markdown.
    Vai direto para geração de apostila → awaiting_approval.
    """
    if not os.path.exists(PASTA_MARKDOWN):
        return JSONResponse(status_code=400, content={"error": "Nenhum markdown encontrado."})

    reset_state()
    pipeline_state["status"] = "running"
    set_stage(5, "done")  # Markdown já está pronto

    def _retomar():
        try:
            # Marca stages anteriores como done
            for i in range(6):
                set_stage(i, "done")

            # Verifica se a apostila já existe — evita regenerar
            pdfs_existentes = []
            if os.path.exists(PASTA_PDF):
                pdfs_existentes = [f for f in os.listdir(PASTA_PDF) if f.endswith(".pdf")]

            if pdfs_existentes:
                # Apostila já existe — só aponta para ela
                set_stage(6, "done")
                pipeline_state["apostila_path"] = os.path.join(PASTA_PDF, pdfs_existentes[0])
                print(f"Apostila existente reutilizada: {pdfs_existentes[0]}")
            else:
                # Gera a apostila
                set_stage(6, "running")
                try:
                    gerar_apostilas_por_curso(
                        pasta_markdown=PASTA_MARKDOWN,
                        pasta_pdf=PASTA_PDF,
                        logo_path=LOGO_PATH
                    )
                    set_stage(6, "done")
                    pdfs = [f for f in os.listdir(PASTA_PDF) if f.endswith(".pdf")]
                    if pdfs:
                        pipeline_state["apostila_path"] = os.path.join(PASTA_PDF, pdfs[0])
                except Exception as e_ap:
                    set_stage(6, "error")
                    print(f"Apostila nao gerada: {e_ap}")

            pipeline_state["status"] = "awaiting_approval"
        except Exception as e:
            pipeline_state["status"] = "error"
            pipeline_state["error"] = str(e)

    threading.Thread(target=_retomar, daemon=True).start()
    return {"message": "Retomando a partir dos markdowns existentes..."}


@app.post("/upload")
async def upload_pdfs(files: list[UploadFile] = File(...)):
    if pipeline_state["status"] == "running":
        return JSONResponse(status_code=400, content={"error": "Pipeline já está em execução."})

    reset_state()
    os.makedirs(PASTA_PDFS, exist_ok=True)

    for file in files:
        path = os.path.join(PASTA_PDFS, file.filename)
        with open(path, "wb") as f:
            f.write(await file.read())

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    return {"message": f"{len(files)} PDF(s) recebido(s). Pipeline iniciado."}


@app.get("/status")
def get_status():
    return {
        "status":              pipeline_state["status"],
        "stage":               pipeline_state["stage"],
        "stages":              pipeline_state["stages"],
        "error":               pipeline_state["error"],
        "videos":              list(pipeline_state["video_paths"].keys()),
        "scenes":              pipeline_state.get("scenes", []),
        "all_disciplines":     pipeline_state.get("all_disciplines", []),
        "selected_disciplines":pipeline_state.get("selected_disciplines", []),
        "current_discipline":  pipeline_state.get("current_discipline"),
        "done_disciplines":    pipeline_state.get("done_disciplines", 0),
        "total_disciplines":   pipeline_state.get("total_disciplines", 0),
    }


@app.get("/disciplines")
def get_disciplines():
    """Lista todas as disciplinas encontradas no PDF carregado."""
    discs = pipeline_state.get("all_disciplines", [])
    if not discs:
        return JSONResponse(status_code=404, content={"error": "Nenhuma disciplina disponível ainda."})
    return {"disciplines": discs}


@app.post("/select-disciplines")
async def select_disciplines(body: dict = {}):
    """
    Recebe as disciplinas selecionadas pelo usuário e continua o pipeline
    (stages 5–7) apenas com elas.
    Body: { "selected": ["Disciplina A", "Disciplina B", ...] }
    """
    if pipeline_state["status"] != "awaiting_discipline_selection":
        return JSONResponse(status_code=400, content={"error": f"Estado inválido: {pipeline_state['status']}"})

    selecionadas = body.get("selected", pipeline_state.get("all_disciplines", []))
    if not selecionadas:
        return JSONResponse(status_code=400, content={"error": "Selecione ao menos uma disciplina."})

    thread = threading.Thread(target=run_pipeline_content, args=(selecionadas,), daemon=True)
    thread.start()

    return {"message": f"{len(selecionadas)} disciplina(s) selecionada(s). Gerando conteúdo..."}


@app.get("/download/apostila")
def download_apostila():
    path = pipeline_state.get("apostila_path")
    if not path or not os.path.exists(path):
        return JSONResponse(status_code=404, content={"error": "Apostila não encontrada."})
    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))


@app.post("/approve")
def approve():
    if pipeline_state["status"] != "awaiting_approval":
        return JSONResponse(status_code=400, content={"error": "Pipeline não está aguardando aprovação."})

    pipeline_state["status"] = "running"
    thread = threading.Thread(target=run_video, daemon=True)
    thread.start()

    return {"message": "Aprovado. Gerando roteiros de produção..."}


@app.post("/reject")
def reject():
    reset_state()
    return {"message": "Pipeline resetado. Faça novo upload."}


@app.get("/scripts")
def get_scripts():
    """Retorna os roteiros gerados, prontos para revisão."""
    scripts = pipeline_state.get("scripts", {})
    if not scripts:
        return JSONResponse(status_code=404, content={"error": "Nenhum roteiro disponível."})
    return {"scripts": scripts}


@app.post("/approve/scripts")
async def approve_scripts(body: dict = {}):
    """
    Recebe os roteiros editados, parseia cenas e aguarda aprovação das cenas.
    Body: { "scripts": { "chave": { "nome": ..., "roteiro": ... }, ... } }
    """
    if pipeline_state["status"] != "awaiting_scripts_approval":
        return JSONResponse(status_code=400, content={"error": f"Estado inválido: {pipeline_state['status']}"})

    if "scripts" in body:
        pipeline_state["scripts"] = body["scripts"]

    # Parseia as cenas de todos os roteiros aprovados
    todos_roteiros = pipeline_state["scripts"]
    roteiro_unificado = "\n\n".join(
        f"DISCIPLINA: {v['nome']}\n{v['roteiro']}"
        for v in todos_roteiros.values()
    )
    cenas = parsear_cenas_do_roteiro(roteiro_unificado)
    pipeline_state["scenes"]  = cenas
    pipeline_state["status"]  = "awaiting_scenes_approval"

    # Persiste cenas em disco para retomada futura
    with open(ARQUIVO_CENAS, "w", encoding="utf-8") as f:
        json.dump(cenas, f, ensure_ascii=False, indent=2)

    return {"message": f"Roteiros aprovados. {len(cenas)} disciplina(s) com cenas prontas para revisão."}


@app.post("/approve/scenes")
async def approve_scenes_pipeline(body: dict = {}):
    """
    Recebe as cenas editadas (com seleção) e dispara geração dos vídeos.
    Body: { "scenes": [ { "disciplina": ..., "cenas": [...], "selecionada": true }, ... ] }
    """
    if pipeline_state["status"] != "awaiting_scenes_approval":
        return JSONResponse(status_code=400, content={"error": f"Estado inválido: {pipeline_state['status']}"})

    cenas_aprovadas = body.get("scenes", pipeline_state["scenes"])
    pipeline_state["scenes"] = cenas_aprovadas

    thread = threading.Thread(target=run_heygen_videos, args=(cenas_aprovadas,), daemon=True)
    thread.start()

    selecionadas = sum(1 for c in cenas_aprovadas if c.get("selecionada", True))
    return {"message": f"Cenas aprovadas. Gerando {selecionadas} vídeo(s) no HeyGen..."}


# ✅ NOVO — lista todos os vídeos prontos
@app.get("/videos")
def list_videos():
    paths = pipeline_state.get("video_paths", {})
    if not paths:
        return JSONResponse(status_code=404, content={"error": "Nenhum vídeo encontrado."})
    return {"videos": list(paths.keys())}


# ✅ NOVO — baixa vídeo por nome da disciplina
@app.get("/download/video/{nome}")
def download_video_por_nome(nome: str):
    paths = pipeline_state.get("video_paths", {})
    path = paths.get(nome)
    if not path or not os.path.exists(path):
        return JSONResponse(status_code=404, content={"error": f"Vídeo '{nome}' não encontrado."})
    return FileResponse(path, media_type="video/mp4", filename=f"{nome}.mp4")


# ✅ MANTIDO por compatibilidade com frontend antigo
@app.get("/download/video")
def download_video():
    path = pipeline_state.get("video_path")
    if not path or not os.path.exists(path):
        return JSONResponse(status_code=404, content={"error": "Vídeo não encontrado."})
    return FileResponse(path, media_type="video/mp4", filename=os.path.basename(path))


# =============================================================================
# GERADOR DE VÍDEOS DIRETO — /gerador-videos/*
# Fluxo com aprovação por etapa: PDF → MD → Roteiro → Cenas → Vídeo
# =============================================================================

_jobs: dict[str, dict] = {}

PASTA_JOBS = "data/output/jobs"


def _pasta_job(job_id: str) -> str:
    pasta = os.path.join(PASTA_JOBS, job_id)
    os.makedirs(pasta, exist_ok=True)
    return pasta


def salvar_job(job_id: str):
    """
    Persiste em disco o estado atual do job e seus artefatos.

    Estrutura gerada:
      data/output/jobs/{job_id}/
        job.json       ← estado completo (permite retomar)
        markdown.md    ← gerado após etapa 1
        roteiro.md     ← gerado após etapa 3
        cenas.json     ← gerado após etapa 5
        videos/        ← preenchida após etapa 7
    """
    job   = _jobs.get(job_id)
    if not job:
        return

    pasta = _pasta_job(job_id)

    # Estado completo
    with open(os.path.join(pasta, "job.json"), "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2, default=str)

    # Artefatos textuais
    if job.get("markdown"):
        with open(os.path.join(pasta, "markdown.md"), "w", encoding="utf-8") as f:
            f.write(job["markdown"])

    if job.get("script"):
        with open(os.path.join(pasta, "roteiro.md"), "w", encoding="utf-8") as f:
            f.write(job["script"])

    if job.get("scenes"):
        with open(os.path.join(pasta, "cenas.json"), "w", encoding="utf-8") as f:
            json.dump(job["scenes"], f, ensure_ascii=False, indent=2)


def _extrair_em_background(job_id: str, caminho_pdf: str):
    """Etapa 1: extrai o texto do PDF e usa Gemini para estruturar em Markdown."""
    try:
        gemini_token = os.getenv("GEMINI_API_KEY")
        resultado = extrair_markdown_do_pdf(caminho_pdf, gemini_token)
        _jobs[job_id].update({
            "state":      "awaiting_md_approval",
            "disciplina": resultado["disciplina"],
            "ementa":     resultado["ementa"],
            "markdown":   resultado["markdown"],
        })
        salvar_job(job_id)
    except Exception as e:
        _jobs[job_id].update({"state": "error", "erro": str(e)})
        salvar_job(job_id)
    finally:
        try:
            os.remove(caminho_pdf)
        except Exception:
            pass


def _gerar_roteiro_em_background(job_id: str):
    """Etapa 3: gera o roteiro a partir do markdown aprovado."""
    job          = _jobs[job_id]
    gemini_token = os.getenv("GEMINI_API_KEY")
    try:
        script = gerar_roteiro(job["markdown"], job["disciplina"], gemini_token)
        _jobs[job_id].update({"state": "awaiting_script_approval", "script": script})
        salvar_job(job_id)
    except Exception as e:
        _jobs[job_id].update({"state": "error", "erro": str(e)})
        salvar_job(job_id)


def _gerar_cenas_em_background(job_id: str):
    """
    Etapa 5: parseia o roteiro aprovado e extrai a estrutura de cenas.
    Sem chamada ao Gemini — instantâneo, zero tokens extras.
    """
    job = _jobs[job_id]
    try:
        cenas = parsear_cenas_do_roteiro(job["script"])
        if not cenas:
            raise ValueError(
                "Nenhuma cena encontrada no roteiro. "
                "Certifique-se de que o roteiro usa o formato [CENA N — nome] e [FALA] texto."
            )
        _jobs[job_id].update({"state": "awaiting_scenes_approval", "scenes": cenas})
        salvar_job(job_id)
    except Exception as e:
        _jobs[job_id].update({"state": "error", "erro": str(e)})
        salvar_job(job_id)


def _gerar_video_em_background(job_id: str):
    """
    Etapa 7: extrai as falas das disciplinas SELECIONADAS e gera um vídeo
    por disciplina no HeyGen. Salva os vídeos na pasta do job.
    """
    job          = _jobs[job_id]
    heygen_token = os.getenv("HEYGEN_API_KEY")
    pasta        = _pasta_job(job_id)
    pasta_videos = os.path.join(pasta, "videos")
    os.makedirs(pasta_videos, exist_ok=True)

    try:
        # Filtra apenas disciplinas selecionadas
        cenas = job.get("scenes", [])
        if isinstance(cenas, list):
            cenas_selecionadas = [d for d in cenas if d.get("selecionada", True)]
        else:
            cenas_selecionadas = cenas

        falas_por_disciplina = extrair_falas_do_roteiro(cenas_selecionadas)

        if not falas_por_disciplina:
            raise ValueError(
                "Nenhuma fala encontrada nas disciplinas selecionadas. "
                "Verifique se as disciplinas estão marcadas e se as falas estão preenchidas."
            )

        videos = []
        for disciplina, fala in falas_por_disciplina.items():
            video_id = gerar_video_heygen(fala, disciplina, heygen_token)
            info     = aguardar_video(video_id, heygen_token)

            # Salva o vídeo em disco
            slug          = re.sub(r"[^\w]", "_", disciplina)[:60]
            caminho_video = os.path.join(pasta_videos, f"{slug}.mp4")
            if info.get("video_url"):
                import requests as req
                video_bytes = req.get(info["video_url"], timeout=60).content
                with open(caminho_video, "wb") as f:
                    f.write(video_bytes)

            videos.append({
                "disciplina":    disciplina,
                "video_id":      video_id,
                "video_url":     info.get("video_url"),
                "duration":      info.get("duration"),
                "caminho_local": caminho_video,
            })

        _jobs[job_id].update({
            "state":   "completed",
            "videos":  videos,
            "video_url": videos[0]["video_url"] if videos else None,
            "duration":  videos[0]["duration"]  if videos else None,
        })
        salvar_job(job_id)

    except Exception as e:
        _jobs[job_id].update({"state": "error", "erro": str(e)})
        salvar_job(job_id)


# ─── Iniciar job ──────────────────────────────────────────────────────────────

@app.post("/gerador-videos/iniciar")
async def gerador_iniciar(file: UploadFile = File(...)):
    """Recebe o PDF e inicia a extração (etapa 1)."""
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(status_code=400, content={"error": "Apenas PDFs são aceitos."})

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        caminho_pdf = tmp.name

    job = novo_job()
    _jobs[job["job_id"]] = job

    threading.Thread(
        target=_extrair_em_background,
        args=(job["job_id"], caminho_pdf),
        daemon=True,
    ).start()

    return {"job_id": job["job_id"]}


# ─── Status ──────────────────────────────────────────────────────────────────

@app.get("/gerador-videos/status/{job_id}")
def gerador_status(job_id: str):
    """Retorna o job completo (state + conteúdos de cada etapa)."""
    job = _jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job não encontrado."})
    return job


# ─── Aprovações ───────────────────────────────────────────────────────────────

class AprovacaoMarkdown(dict):
    pass


@app.post("/gerador-videos/aprovar-markdown/{job_id}")
async def aprovar_markdown(job_id: str, body: dict = {}):
    """
    Etapa 2 → 3: usuário aprova (ou edita) o markdown.
    Body opcional: { "markdown": "conteúdo editado" }
    """
    job = _jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job não encontrado."})
    if job["state"] != "awaiting_md_approval":
        return JSONResponse(status_code=400, content={"error": f"Estado inválido: {job['state']}"})

    if "markdown" in body:
        _jobs[job_id]["markdown"] = body["markdown"]

    _jobs[job_id]["state"] = "generating_script"
    threading.Thread(target=_gerar_roteiro_em_background, args=(job_id,), daemon=True).start()
    return {"message": "Markdown aprovado. Gerando roteiro..."}


@app.post("/gerador-videos/aprovar-roteiro/{job_id}")
async def aprovar_roteiro(job_id: str, body: dict = {}):
    """
    Etapa 4 → 5: usuário aprova (ou edita) o roteiro.
    Body opcional: { "script": "roteiro editado" }
    """
    job = _jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job não encontrado."})
    if job["state"] != "awaiting_script_approval":
        return JSONResponse(status_code=400, content={"error": f"Estado inválido: {job['state']}"})

    if "script" in body:
        _jobs[job_id]["script"] = body["script"]

    _jobs[job_id]["state"] = "generating_scenes"
    threading.Thread(target=_gerar_cenas_em_background, args=(job_id,), daemon=True).start()
    return {"message": "Roteiro aprovado. Gerando plano de cenas..."}


@app.post("/gerador-videos/aprovar-cenas/{job_id}")
async def aprovar_cenas(job_id: str, body: dict = {}):
    """
    Etapa 6 → 7: usuário aprova (ou edita) as falas por cena.
    Body opcional: { "scenes": [...] }  — lista de disciplinas com cenas editadas
    Após aprovação, envia para o HeyGen (uma chamada por disciplina).
    """
    job = _jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job não encontrado."})
    if job["state"] != "awaiting_scenes_approval":
        return JSONResponse(status_code=400, content={"error": f"Estado inválido: {job['state']}"})

    if "scenes" in body:
        _jobs[job_id]["scenes"] = body["scenes"]

    _jobs[job_id]["state"] = "generating_video"
    threading.Thread(target=_gerar_video_em_background, args=(job_id,), daemon=True).start()
    return {"message": "Cenas aprovadas. Gerando vídeo no HeyGen..."}


# ─── HeyGen status direto ────────────────────────────────────────────────────

@app.get("/gerador-videos/heygen-status/{video_id}")
def gerador_heygen_status(video_id: str):
    """Consulta status de um video_id direto no HeyGen v3."""
    heygen_token = os.getenv("HEYGEN_API_KEY")
    if not heygen_token:
        return JSONResponse(status_code=500, content={"error": "HEYGEN_API_KEY não configurado."})
    try:
        return verificar_status_video(video_id, heygen_token)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})