"""
api.py — Backend San Marino Booklet Creator
Porta: 8000

Endpoints:
  POST /upload                               → recebe PDFs, dispara pipeline em background
  GET  /status                               → status do pipeline (polling do ProcessingStep)
  GET  /download/apostila                    → baixa a apostila gerada (PDF)
  POST /approve                              → aprova conteúdo e dispara geração real de vídeo
  POST /reject                               → rejeita e reseta o pipeline
  POST /approve/script                       → aprova roteiros (ScriptApprovalStep)
  POST /reject/script                        → rejeita roteiros e reseta
  POST /redo                                 → reexecuta pipeline com sugestões do usuário
  GET  /videos                               → lista vídeos gerados (por disciplina)
  GET  /download/video/{nome}                → baixa vídeo por nome de disciplina ou arquivo
  GET  /cursos                               → lista cursos + apostilas (CourseDashboard)
  GET  /download/apostila/{nome}             → baixa apostila por nome de arquivo

  (fluxo GeradorVideos com aprovação por etapa)
  POST /gerador-videos/iniciar               → inicia job: PDF → Markdown via OpenAI
  GET  /gerador-videos/status/{job_id}       → polling do job
  POST /gerador-videos/aprovar-markdown/{job_id}
  POST /gerador-videos/aprovar-roteiro/{job_id}
  POST /gerador-videos/aprovar-cenas/{job_id}
  GET  /gerador-videos/heygen-status/{video_id}  → consulta status direto no HeyGen v3

Rodar:
  uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import io
import os
import re
import json
import zipfile
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

# Pipeline principal
from src.video_generator.pipeline_video import gerar_videos_por_disciplina

# Gerador de vídeos direto (máquina de estados com aprovação por etapa)
from src.video_generator.gerador_videos_direto import (
    novo_job,
    extrair_markdown_do_pdf,
    gerar_roteiro,
    parsear_cenas_do_roteiro,
    verificar_status_video,
)
from src.video_generator.video_generator import gerar_video_com_slides

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR      = Path(__file__).parent
DATA_INPUT    = BASE_DIR / "data" / "input"
DATA_CSV      = BASE_DIR / "data" / "input" / "planilhas_geradas"
DATA_JSON     = BASE_DIR / "data" / "output" / "json"
DATA_FAISS    = BASE_DIR / "data" / "output" / "faiss"
DATA_MARKDOWN = BASE_DIR / "data" / "output" / "markdown"
DATA_PDF      = BASE_DIR / "data" / "output" / "workbooks_pdf"
DATA_VIDEO    = BASE_DIR / "data" / "output" / "videos"
PASTA_JOBS    = BASE_DIR / "data" / "output" / "jobs"
LOGO_PATH     = BASE_DIR / "assets" / "logo.jpeg"

for d in [DATA_INPUT, DATA_CSV, DATA_JSON, DATA_FAISS, DATA_MARKDOWN,
          DATA_PDF, DATA_VIDEO, PASTA_JOBS]:
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="San Marino Booklet Creator API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Estado global do pipeline principal
# ---------------------------------------------------------------------------
STAGE_NAMES = [
    "Extração de PDF",
    "Carregamento Base",
    "Embeddings",
    "Índice FAISS",
    "Setup LLM",
    "Geração Markdown",
    "PDF da Apostila",
    "Geração de Vídeo",
]

pipeline_state: dict = {
    "status":         "idle",   # idle | running | awaiting_approval | done | error
    "stage":          0,
    "stages":         [{"name": n, "status": "waiting"} for n in STAGE_NAMES],
    "error":          None,
    "last_apostila":  None,     # path do PDF mais recente
    "video_paths":    {},       # { nome_disciplina: caminho_absoluto }
    "uploaded_files": [],       # nomes dos PDFs enviados
    "instructions":   "",
}

pipeline_lock = threading.Lock()


def reset_pipeline():
    with pipeline_lock:
        pipeline_state["status"]         = "idle"
        pipeline_state["stage"]          = 0
        pipeline_state["stages"]         = [{"name": n, "status": "waiting"} for n in STAGE_NAMES]
        pipeline_state["error"]          = None
        pipeline_state["last_apostila"]  = None
        pipeline_state["video_paths"]    = {}
        pipeline_state["uploaded_files"] = []
        pipeline_state["instructions"]   = ""


def set_stage(index: int, status: str):
    with pipeline_lock:
        pipeline_state["stage"] = index
        pipeline_state["stages"][index]["status"] = status


# ---------------------------------------------------------------------------
# Pipeline principal em thread
# ---------------------------------------------------------------------------

def run_pipeline(file_paths: list[str], instructions: str):
    """
    Executa as etapas 0-6 (extração → apostila PDF).
    Ao final entra em awaiting_approval para o usuário revisar.
    """
    caminho_json  = str(DATA_JSON / "base_geral.json")
    caminho_index = str(DATA_FAISS / "faiss_index.bin")

    try:
        # Imports dentro do try para capturar erros de dependência ausente
        from src.pdf_csv.pdf_csv import extrair_pdf_para_csv, aplicar_correcoes
        from src.syllabus_extractor.csv_processor import extrair_base_csv
        from src.content_generation.embedding_model import carregar_modelo, gerar_embeddings
        from src.content_generation.faiss_index import criar_ou_carregar_index
        from src.content_generation.rag_pipeline import buscar_chunks
        from src.content_generation.generator import configurar_openai, gerar_documento
        from src.content_generation.area_detector import detectar_area_do_input
        from src.output_formatter.markdown_generator import gerar_markdowns
        from src.workbooks_generator.workbooks_generator import gerar_apostilas_por_curso

        with pipeline_lock:
            pipeline_state["status"]       = "running"
            pipeline_state["instructions"] = instructions

        # ── Etapa 0: Extração de PDF → CSV → registros ───────────────────
        set_stage(0, "running")
        base_geral = []
        for caminho_pdf in file_paths:
            nome_base   = Path(caminho_pdf).stem
            caminho_csv = str(DATA_CSV / (nome_base + ".csv"))
            extrair_pdf_para_csv(caminho_pdf, caminho_csv)
            aplicar_correcoes(caminho_csv)
            registros = extrair_base_csv(caminho_pdf, str(DATA_CSV), str(DATA_JSON))
            if not registros:
                raise Exception(
                    f"Nenhum registro extraído de '{Path(caminho_pdf).name}'. "
                    "Verifique se o PDF contém tabelas com Disciplina / Ementa / Conteúdo."
                )
            det = detectar_area_do_input(caminho_pdf, client=None)
            area_key = det["area_key"]
            for r in registros:
                r["area"] = area_key
            base_geral.extend(registros)
        with open(caminho_json, "w", encoding="utf-8") as f:
            json.dump(base_geral, f, ensure_ascii=False, indent=2)
        set_stage(0, "done")

        # ── Etapa 1: Validação da base ────────────────────────────────────
        set_stage(1, "running")
        if not base_geral:
            raise Exception("Base vazia após extração.")
        print(f"✅ {len(base_geral)} registros carregados")
        set_stage(1, "done")

        # ── Etapa 2: Embeddings ───────────────────────────────────────────
        set_stage(2, "running")
        model      = carregar_modelo()
        embeddings = gerar_embeddings(model, base_geral)
        set_stage(2, "done")

        # ── Etapa 3: Índice FAISS ─────────────────────────────────────────
        set_stage(3, "running")
        index = criar_ou_carregar_index(
            caminho_index, embeddings,
            forcar_rebuild=True,
            n_registros=len(base_geral),
        )
        set_stage(3, "done")

        # ── Etapa 4: Setup LLM ────────────────────────────────────────────
        set_stage(4, "running")
        llm = configurar_openai()
        set_stage(4, "done")

        # ── Etapa 5: Geração Markdown ─────────────────────────────────────
        set_stage(5, "running")
        gerar_markdowns(
            base_geral=base_geral,
            buscar_chunks=buscar_chunks,
            gerar_documento=gerar_documento,
            model=model,
            index=index,
            gemini=llm,
            pasta_saida=str(DATA_MARKDOWN),
            force=True,
            instructions=instructions,
        )
        set_stage(5, "done")

        # ── Etapa 6: PDF da Apostila ──────────────────────────────────────
        set_stage(6, "running")
        gerar_apostilas_por_curso(
            pasta_markdown=str(DATA_MARKDOWN),
            pasta_pdf=str(DATA_PDF),
            logo_path=str(LOGO_PATH),
        )
        # Registra o primeiro PDF gerado como apostila disponível para download
        pdfs = sorted(DATA_PDF.rglob("*.pdf"))
        if pdfs:
            with pipeline_lock:
                pipeline_state["last_apostila"] = str(pdfs[-1])
        set_stage(6, "done")

        with pipeline_lock:
            pipeline_state["status"] = "awaiting_approval"

    except Exception as e:
        tb = traceback.format_exc()
        print(f"❌ Pipeline error:\n{tb}")
        with pipeline_lock:
            pipeline_state["status"] = "error"
            pipeline_state["error"]  = f"{e}\n\nDetalhes:\n{tb}"
            idx = pipeline_state["stage"]
            if 0 <= idx < len(STAGE_NAMES):
                pipeline_state["stages"][idx]["status"] = "error"


def run_video():
    """
    Etapa 7: gera os vídeos usando pipeline_video.py (roteiro via OpenAI + HeyGen v3, multi-cena).
    Disparado após /approve.
    """
    try:
        set_stage(7, "running")
        openai_token = os.getenv("OPENAI_API_KEY")
        heygen_token = os.getenv("HEYGEN_API_KEY")

        if not heygen_token:
            raise Exception("HEYGEN_API_KEY não encontrada. Configure no .env.")

        gerar_videos_por_disciplina(
            pasta_markdown=str(DATA_MARKDOWN),
            pasta_saida=str(DATA_VIDEO),
            openai_token=openai_token,
            heyGen_token=heygen_token,
        )
        set_stage(7, "done")

        # Indexa os vídeos gerados por nome de disciplina (pasta pai do arquivo)
        video_paths: dict[str, str] = {}
        for root, _, files in os.walk(str(DATA_VIDEO)):
            for f in files:
                if f.lower().endswith((".mp4", ".avi", ".mov", ".webm")):
                    disciplina = os.path.basename(root)
                    video_paths[disciplina] = os.path.join(root, f)

        with pipeline_lock:
            pipeline_state["video_paths"] = video_paths
            pipeline_state["status"]      = "done"

    except Exception as e:
        with pipeline_lock:
            pipeline_state["status"] = "error"
            pipeline_state["error"]  = str(e)
        set_stage(7, "error")


# ---------------------------------------------------------------------------
# ── ROTAS PRINCIPAIS ────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload_pdfs(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    instructions: str = Form(""),
    suggestions: str = Form(""),
):
    if not files:
        raise HTTPException(400, "Nenhum arquivo enviado.")

    reset_pipeline()
    saved_paths = []

    for upload in files:
        if not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"Arquivo '{upload.filename}' não é um PDF.")
        dest = DATA_INPUT / upload.filename
        dest.write_bytes(await upload.read())
        saved_paths.append(str(dest))

    with pipeline_lock:
        pipeline_state["uploaded_files"] = [Path(p).name for p in saved_paths]

    effective_instructions = instructions
    if suggestions:
        effective_instructions += f"\n\nSugestões de alteração do usuário: {suggestions}"

    threading.Thread(
        target=run_pipeline,
        args=(saved_paths, effective_instructions),
        daemon=True,
    ).start()

    return {"ok": True, "files": [Path(p).name for p in saved_paths]}


@app.get("/status")
async def get_status():
    with pipeline_lock:
        return {
            "status": pipeline_state["status"],
            "stage":  pipeline_state["stage"],
            "stages": pipeline_state["stages"],
            "error":  pipeline_state["error"],
            "videos": list(pipeline_state["video_paths"].keys()),
        }


@app.get("/download/apostila")
async def download_apostila():
    with pipeline_lock:
        apostila = pipeline_state.get("last_apostila")

    if not apostila or not Path(apostila).exists():
        pdfs = sorted(DATA_PDF.rglob("*.pdf"))
        if not pdfs:
            raise HTTPException(404, "Nenhuma apostila gerada ainda.")
        apostila = str(pdfs[-1])

    path = Path(apostila)
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@app.get("/download/apostilas-zip")
async def download_apostilas_zip():
    """Empacota todo o conteúdo de workbooks_pdf/aluno em um ZIP e devolve para download."""
    aluno_dir = DATA_PDF / "aluno"
    if not aluno_dir.exists():
        raise HTTPException(404, "Nenhuma apostila gerada ainda.")

    pdfs = sorted(aluno_dir.rglob("*.pdf"))
    if not pdfs:
        raise HTTPException(404, "Nenhum PDF encontrado em workbooks_pdf/aluno.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for pdf in pdfs:
            zf.write(pdf, pdf.relative_to(aluno_dir))
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="apostilas_aluno.zip"'},
    )


@app.post("/approve")
async def approve_content():
    """Aprova o conteúdo e dispara a geração real de vídeo em background."""
    with pipeline_lock:
        if pipeline_state["status"] != "awaiting_approval":
            raise HTTPException(400, "Pipeline não está aguardando aprovação.")
        pipeline_state["status"] = "running"

    threading.Thread(target=run_video, daemon=True).start()
    return {"ok": True, "message": "Aprovado. Gerando vídeos..."}


@app.post("/reject")
async def reject_content():
    reset_pipeline()
    return {"ok": True, "message": "Pipeline resetado."}


@app.post("/approve/script")
async def approve_script():
    with pipeline_lock:
        if pipeline_state["status"] not in ("done", "awaiting_approval"):
            raise HTTPException(400, "Pipeline não está em estado de aprovação de roteiro.")
    return {"ok": True, "message": "Roteiros aprovados."}


@app.post("/reject/script")
async def reject_script():
    reset_pipeline()
    return {"ok": True, "message": "Roteiros rejeitados. Pipeline resetado."}


class RedoBody(BaseModel):
    suggestions: str = ""


@app.post("/redo")
async def redo_pipeline(body: RedoBody):
    """Re-executa o pipeline com os arquivos já salvos + sugestões do usuário."""
    with pipeline_lock:
        saved_names = list(pipeline_state.get("uploaded_files", []))

    if not saved_names:
        raise HTTPException(400, "Nenhum arquivo encontrado. Faça upload novamente.")

    existing = [str(DATA_INPUT / n) for n in saved_names if (DATA_INPUT / n).exists()]
    if not existing:
        raise HTTPException(400, "Arquivos originais não encontrados. Faça upload novamente.")

    effective_instructions = ""
    if body.suggestions:
        effective_instructions = f"\n\nSugestões de alteração do usuário: {body.suggestions}"

    reset_pipeline()
    with pipeline_lock:
        pipeline_state["uploaded_files"] = saved_names

    threading.Thread(
        target=run_pipeline,
        args=(existing, effective_instructions),
        daemon=True,
    ).start()
    return {"ok": True}


@app.get("/videos")
async def list_videos():
    """Lista vídeos disponíveis por nome de disciplina."""
    with pipeline_lock:
        video_paths = dict(pipeline_state.get("video_paths", {}))

    if video_paths:
        return {"videos": sorted(video_paths.keys())}

    # Fallback: varre o filesystem (vídeos de sessões anteriores)
    # Usa o nome da subpasta como disciplina, igual ao que run_video() indexa.
    disciplinas: set[str] = set()
    data_video_str = str(DATA_VIDEO)
    for root, _, files in os.walk(data_video_str):
        if root == data_video_str:
            continue  # ignora arquivos soltos na raiz
        for f in files:
            if f.lower().endswith((".mp4", ".avi", ".mov", ".webm")):
                disciplinas.add(os.path.basename(root))
    return {"videos": sorted(disciplinas)}


@app.get("/download/video/{nome}")
async def download_video(nome: str):
    """Baixa vídeo por nome de disciplina (estado) ou nome de arquivo (fallback)."""
    with pipeline_lock:
        video_paths = dict(pipeline_state.get("video_paths", {}))

    # Tenta por nome de disciplina
    path_str = video_paths.get(nome)
    if path_str and Path(path_str).exists():
        path = Path(path_str)
        return FileResponse(
            path=str(path),
            media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
        )

    # Fallback: busca por nome de arquivo dentro de DATA_VIDEO
    matches = list(DATA_VIDEO.rglob(nome))
    if not matches:
        raise HTTPException(404, f"Vídeo '{nome}' não encontrado.")
    path = matches[0]
    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


# ---------------------------------------------------------------------------
# ── DASHBOARD ───────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@app.get("/cursos")
async def list_cursos():
    # gerar_apostilas_por_curso cria: workbooks_pdf/aluno/<curso>/<disciplina>.pdf
    # Iteramos apenas o subdiretório "aluno" para listar cursos do caderno do aluno.
    aluno_dir = DATA_PDF / "aluno"
    if not aluno_dir.exists():
        return {"cursos": []}

    cursos = []
    for entry in sorted(aluno_dir.iterdir()):
        if not entry.is_dir():
            continue
        apostilas = []
        for pdf in sorted(entry.glob("*.pdf")):
            stat = pdf.stat()
            apostilas.append({
                "nome":   pdf.name,
                "data":   datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                "status": "gerada",
            })
        cursos.append({"nome": entry.name, "pasta": entry.name, "apostilas": apostilas})
    return {"cursos": cursos}


@app.get("/download/apostila/{nome_arquivo}")
async def download_apostila_por_nome(nome_arquivo: str):
    matches = list(DATA_PDF.rglob(nome_arquivo))
    if not matches:
        raise HTTPException(404, f"Apostila '{nome_arquivo}' não encontrada.")
    path = matches[0]
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


# ---------------------------------------------------------------------------
# ── GERADOR DE VÍDEOS DIRETO (/gerador-videos/*) ────────────────────────────
# Fluxo: PDF → Markdown → Roteiro → Cenas → Vídeo HeyGen
# Cada etapa aguarda aprovação do usuário antes de avançar.
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}


def _pasta_job(job_id: str) -> Path:
    pasta = PASTA_JOBS / job_id
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def salvar_job(job_id: str):
    """Persiste o estado do job e seus artefatos em disco."""
    job = _jobs.get(job_id)
    if not job:
        return
    pasta = _pasta_job(job_id)

    with open(pasta / "job.json", "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2, default=str)

    if job.get("markdown"):
        (pasta / "markdown.md").write_text(job["markdown"], encoding="utf-8")
    if job.get("script"):
        (pasta / "roteiro.md").write_text(job["script"], encoding="utf-8")
    if job.get("scenes"):
        with open(pasta / "cenas.json", "w", encoding="utf-8") as f:
            json.dump(job["scenes"], f, ensure_ascii=False, indent=2)


def _extrair_em_background(job_id: str, caminho_pdf: str):
    """Etapa 1: extrai texto do PDF e estrutura em Markdown via OpenAI."""
    try:
        openai_token = os.getenv("OPENAI_API_KEY")
        resultado = extrair_markdown_do_pdf(caminho_pdf, openai_token)
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
    """Etapa 3: gera roteiro de produção a partir do markdown aprovado via OpenAI."""
    job          = _jobs[job_id]
    openai_token = os.getenv("OPENAI_API_KEY")
    try:
        script = gerar_roteiro(job["markdown"], job["disciplina"], openai_token)
        _jobs[job_id].update({"state": "awaiting_script_approval", "script": script})
        salvar_job(job_id)
    except Exception as e:
        _jobs[job_id].update({"state": "error", "erro": str(e)})
        salvar_job(job_id)


def _gerar_cenas_em_background(job_id: str):
    """Etapa 5: parseia o roteiro aprovado e extrai estrutura de cenas (sem LLM)."""
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
    Etapa 7: gera o vídeo completo para cada disciplina selecionada — slides
    (PNG por cena) + avatar HeyGen recortado (tronco pra cima) e posicionado
    no canto + legenda queimada. Mesmo pipeline usado em test_video_um.py
    (ver video_generator.gerar_video_com_slides / compor_avatar_slides.py).
    """
    job          = _jobs[job_id]
    heygen_token = os.getenv("HEYGEN_API_KEY")
    openai_token = os.getenv("OPENAI_API_KEY")
    pasta        = _pasta_job(job_id)
    pasta_videos = pasta / "videos"
    pasta_videos.mkdir(exist_ok=True)

    try:
        disciplinas = job.get("scenes", [])
        disciplinas_selecionadas = (
            [d for d in disciplinas if d.get("selecionada", True)]
            if isinstance(disciplinas, list) else disciplinas
        )
        if not disciplinas_selecionadas:
            raise ValueError(
                "Nenhuma disciplina selecionada. "
                "Verifique se as disciplinas estão marcadas e se as falas estão preenchidas."
            )

        videos = []
        for disc in disciplinas_selecionadas:
            disciplina = disc.get("disciplina", "Disciplina")
            cenas = [c for c in disc.get("cenas", []) if c.get("fala")]
            if not cenas:
                print(f"   [AVISO] Disciplina '{disciplina}' sem falas — pulando")
                continue

            slug             = re.sub(r"[^\w]", "_", disciplina)[:60]
            pasta_disciplina = pasta_videos / slug
            pasta_disciplina.mkdir(exist_ok=True)
            pasta_slides     = pasta_disciplina / "slides"

            caminho_video = str(pasta_videos / f"{slug}.mp4")
            gerar_video_com_slides(
                cenas=cenas,
                disciplina=disciplina,
                caminho_saida=caminho_video,
                pasta_slides=str(pasta_slides),
                heygen_token=heygen_token,
                openai_token=openai_token,
            )

            videos.append({
                "disciplina":    disciplina,
                "caminho_local": caminho_video,
            })

        if not videos:
            raise ValueError("Nenhum vídeo gerado — verifique as falas das disciplinas selecionadas.")

        _jobs[job_id].update({
            "state":     "completed",
            "videos":    videos,
            "video_url": None,
            "duration":  None,
        })
        salvar_job(job_id)

    except Exception as e:
        _jobs[job_id].update({"state": "error", "erro": str(e)})
        salvar_job(job_id)


# ─── Rotas /gerador-videos/* ─────────────────────────────────────────────────

@app.post("/gerador-videos/iniciar")
async def gerador_iniciar(file: UploadFile = File(...)):
    """Recebe o PDF e inicia a extração de Markdown (etapa 1)."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF são aceitos.")

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


@app.get("/gerador-videos/status/{job_id}")
def gerador_status(job_id: str):
    """Retorna o job completo (state + conteúdos de cada etapa)."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' não encontrado.")
    return job


@app.post("/gerador-videos/aprovar-markdown/{job_id}")
async def aprovar_markdown(job_id: str, body: dict = {}):
    """
    Etapa 2 → 3: usuário aprova (ou edita) o markdown.
    Body opcional: { "markdown": "conteúdo editado" }
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    if job["state"] != "awaiting_md_approval":
        raise HTTPException(400, f"Estado inválido: {job['state']}")

    if "markdown" in body:
        _jobs[job_id]["markdown"] = body["markdown"]

    _jobs[job_id]["state"] = "generating_script"
    threading.Thread(
        target=_gerar_roteiro_em_background,
        args=(job_id,),
        daemon=True,
    ).start()
    return {"message": "Markdown aprovado. Gerando roteiro..."}


@app.post("/gerador-videos/aprovar-roteiro/{job_id}")
async def aprovar_roteiro(job_id: str, body: dict = {}):
    """
    Etapa 4 → 5: usuário aprova (ou edita) o roteiro.
    Body opcional: { "script": "roteiro editado" }
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    if job["state"] != "awaiting_script_approval":
        raise HTTPException(400, f"Estado inválido: {job['state']}")

    if "script" in body:
        _jobs[job_id]["script"] = body["script"]

    _jobs[job_id]["state"] = "generating_scenes"
    threading.Thread(
        target=_gerar_cenas_em_background,
        args=(job_id,),
        daemon=True,
    ).start()
    return {"message": "Roteiro aprovado. Gerando plano de cenas..."}


@app.post("/gerador-videos/aprovar-cenas/{job_id}")
async def aprovar_cenas(job_id: str, body: dict = {}):
    """
    Etapa 6 → 7: usuário aprova (ou edita) as falas por cena.
    Body opcional: { "scenes": [...] }
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    if job["state"] != "awaiting_scenes_approval":
        raise HTTPException(400, f"Estado inválido: {job['state']}")

    if "scenes" in body:
        _jobs[job_id]["scenes"] = body["scenes"]

    _jobs[job_id]["state"] = "generating_video"
    threading.Thread(
        target=_gerar_video_em_background,
        args=(job_id,),
        daemon=True,
    ).start()
    return {"message": "Cenas aprovadas. Gerando vídeo no HeyGen..."}


@app.get("/gerador-videos/heygen-status/{video_id}")
def gerador_heygen_status(video_id: str):
    """Consulta status de um video_id direto no HeyGen v3."""
    heygen_token = os.getenv("HEYGEN_API_KEY")
    if not heygen_token:
        raise HTTPException(500, "HEYGEN_API_KEY não configurado.")
    try:
        return verificar_status_video(video_id, heygen_token)
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# ── HEALTH CHECK ────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@app.get("/")
async def health():
    return {
        "status":  "ok",
        "service": "San Marino Booklet Creator API",
        "version": "2.0.0",
        "endpoints": [
            "POST /upload",
            "GET  /status",
            "GET  /download/apostila",
            "POST /approve",
            "POST /reject",
            "POST /approve/script",
            "POST /reject/script",
            "POST /redo",
            "GET  /videos",
            "GET  /download/video/{nome}",
            "GET  /cursos",
            "GET  /download/apostila/{nome_arquivo}",
            "POST /gerador-videos/iniciar",
            "GET  /gerador-videos/status/{job_id}",
            "POST /gerador-videos/aprovar-markdown/{job_id}",
            "POST /gerador-videos/aprovar-roteiro/{job_id}",
            "POST /gerador-videos/aprovar-cenas/{job_id}",
            "GET  /gerador-videos/heygen-status/{video_id}",
        ],
    }


# ---------------------------------------------------------------------------
# ── ENTRYPOINT ───────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
