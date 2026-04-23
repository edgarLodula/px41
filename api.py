import os
import json
import threading
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

# =========================
# PATHS
# =========================
PASTA_PDFS     = "data/input"
PASTA_JSON     = "data/output/json"
PASTA_INDEX    = "data/output/faiss"
PASTA_MARKDOWN = "data/output/markdown"
PASTA_PDF      = "data/output/workbooks_pdf"
PASTA_VIDEO    = "data/output/videos"
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
    "status": "idle",  # idle | running | awaiting_approval | done | error
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
    "video_path": None,   # mantido por compatibilidade
    "video_paths": {},    # ✅ NOVO — dicionário { nome_disciplina: caminho_absoluto }
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
    pipeline_state["video_paths"] = {}   # ✅ reseta o dicionário também
    for s in pipeline_state["stages"]:
        s["status"] = "waiting"

# =========================
# PIPELINE EM THREAD
# =========================
def run_pipeline():
    try:
        os.makedirs(PASTA_JSON, exist_ok=True)
        os.makedirs(PASTA_INDEX, exist_ok=True)

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

        set_stage(1, "running")
        base_geral = carregar_base(CAMINHO_JSON)
        if not base_geral:
            raise Exception("Base vazia após extração.")
        set_stage(1, "done")

        set_stage(2, "running")
        model = carregar_modelo()
        embeddings = gerar_embeddings(model, base_geral)
        set_stage(2, "done")

        set_stage(3, "running")
        index = criar_ou_carregar_index(CAMINHO_INDEX, embeddings)
        set_stage(3, "done")

        set_stage(4, "running")
        gemini = configurar_gemini()
        set_stage(4, "done")

        set_stage(5, "running")
        gerar_markdowns(
            base_geral=base_geral,
            buscar_chunks=buscar_chunks,
            gerar_documento=gerar_documento,
            model=model,
            index=index,
            gemini=gemini,
            pasta_saida=PASTA_MARKDOWN
        )
        set_stage(5, "done")

        set_stage(6, "running")
        gerar_apostilas_por_curso(
            pasta_markdown=PASTA_MARKDOWN,
            pasta_pdf=PASTA_PDF,
            logo_path=LOGO_PATH
        )
        set_stage(6, "done")

        pdfs = [f for f in os.listdir(PASTA_PDF) if f.endswith(".pdf")]
        if pdfs:
            pipeline_state["apostila_path"] = os.path.join(PASTA_PDF, pdfs[0])

        pipeline_state["status"] = "awaiting_approval"

    except Exception as e:
        pipeline_state["status"] = "error"
        pipeline_state["error"] = str(e)
        for s in pipeline_state["stages"]:
            if s["status"] == "running":
                s["status"] = "error"


def run_video():
    try:
        set_stage(7, "running")
        groq_token = os.getenv("GROQ_TOKEN")
        if not groq_token:
            raise Exception("GROQ_TOKEN não encontrado.")

        gerar_videos_por_disciplina(
            pasta_markdown=PASTA_MARKDOWN,
            pasta_saida=PASTA_VIDEO,
            groq_token=groq_token
        )
        set_stage(7, "done")

        # ✅ CORRIGIDO — salva TODOS os vídeos no dicionário
        print(f"🔍 Procurando vídeos em: {PASTA_VIDEO}")
        print(f"🔍 Pasta existe? {os.path.exists(PASTA_VIDEO)}")

        video_paths = {}
        for root, dirs, files in os.walk(PASTA_VIDEO):
            print(f"📁 Entrando em: {root}")
            print(f"   Arquivos: {files}")
            for f in files:
                if f.endswith((".mp4", ".avi", ".mov")):
                    disciplina = os.path.basename(root)
                    caminho_completo = os.path.join(root, f)
                    print(f"✅ Encontrou: {disciplina} → {caminho_completo}")
                    video_paths[disciplina] = caminho_completo
                    

        print(f"🎬 video_paths final: {video_paths}")
        if video_paths:
            pipeline_state["video_paths"] = video_paths
            pipeline_state["video_path"] = list(video_paths.values())[0]

        pipeline_state["status"] = "done"

    except Exception as e:
        pipeline_state["status"] = "error"
        pipeline_state["error"] = str(e)
        set_stage(7, "error")


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
        "status": pipeline_state["status"],
        "stage": pipeline_state["stage"],
        "stages": pipeline_state["stages"],
        "error": pipeline_state["error"],
        "videos": list(pipeline_state["video_paths"].keys()),  # ✅ lista de disciplinas disponíveis
    }


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

    return {"message": "Aprovado. Gerando vídeos..."}


@app.post("/reject")
def reject():
    reset_state()
    return {"message": "Pipeline resetado. Faça novo upload."}


# ✅ NOVO — lista todos os vídeos prontos
@app.get("/download/videos")
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