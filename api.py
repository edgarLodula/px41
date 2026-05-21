"""
api.py — Backend San Marino Booklet Creator
Porta: 8000

Endpoints cobertos:
  POST /upload                          → recebe PDFs, dispara pipeline em background
  GET  /status                          → status do pipeline (polling do ProcessingStep)
  GET  /download/apostila               → baixa a apostila gerada (PDF)
  POST /approve                         → aprova conteúdo e avança para geração de vídeo
  POST /reject                          → rejeita e reseta o pipeline
  GET  /videos                          → lista vídeos gerados
  GET  /download/video/{nome}           → baixa vídeo por nome
  GET  /cursos                          → lista cursos + apostilas (CourseDashboard)
  GET  /download/apostila/{nome}        → baixa apostila por nome de arquivo

  (rotas do GeradorVideos)
  POST /gerador-videos/iniciar          → inicia job de vídeo avulso
  GET  /gerador-videos/status/{job_id} → polling do job
  POST /gerador-videos/aprovar-markdown/{job_id}
  POST /gerador-videos/aprovar-roteiro/{job_id}
  POST /gerador-videos/aprovar-cenas/{job_id}

Instalar dependências:
  pip install fastapi uvicorn python-multipart aiofiles

Rodar:
  python api.py
  ou
  uvicorn api:app --reload --port 8000
"""

import os
import uuid
import asyncio
import threading
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuração de paths (espelha o main.py)
# ---------------------------------------------------------------------------
BASE_DIR       = Path(__file__).parent
DATA_INPUT     = BASE_DIR / "data" / "input"
DATA_CSV       = BASE_DIR / "data" / "input" / "planilhas_geradas"
DATA_JSON      = BASE_DIR / "data" / "output" / "json"
DATA_FAISS     = BASE_DIR / "data" / "output" / "faiss"
DATA_MARKDOWN  = BASE_DIR / "data" / "output" / "markdown"
DATA_PDF       = BASE_DIR / "data" / "output" / "workbooks_pdf"
DATA_VIDEO     = BASE_DIR / "data" / "output" / "videos"

# Garante que os diretórios existam
for d in [DATA_INPUT, DATA_CSV, DATA_JSON, DATA_FAISS, DATA_MARKDOWN, DATA_PDF, DATA_VIDEO]:
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="San Marino Booklet Creator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Em produção, restrinja para o domínio do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Estado global do pipeline principal (Index.tsx)
# Numa versão real isso seria um banco de dados ou Redis
# ---------------------------------------------------------------------------
STAGE_NAMES = [
    "Extração de PDF",
    "Carregamento Base",
    "Embeddings",
    "Índice FAISS",
    "Setup Gemini",
    "Geração Markdown",
    "PDF da Apostila",
    "Geração de Vídeo",
]

pipeline_state: dict = {
    "status": "idle",          # idle | running | awaiting_approval | done | error
    "stage": 0,
    "stages": [{"name": n, "status": "waiting"} for n in STAGE_NAMES],
    "error": None,
    "last_apostila": None,     # path do PDF mais recente
    "uploaded_files": [],      # lista de nomes dos PDFs enviados
    "instructions": "",        # instruções de alteração vindas do UploadStep
}

pipeline_lock = threading.Lock()


def reset_pipeline():
    """Reseta o estado do pipeline para idle."""
    with pipeline_lock:
        pipeline_state["status"]        = "idle"
        pipeline_state["stage"]         = 0
        pipeline_state["stages"]        = [{"name": n, "status": "waiting"} for n in STAGE_NAMES]
        pipeline_state["error"]         = None
        pipeline_state["last_apostila"] = None
        pipeline_state["uploaded_files"] = []
        pipeline_state["instructions"]  = ""


def set_stage(index: int, status: str):
    """Marca um estágio como running/done/error."""
    with pipeline_lock:
        pipeline_state["stage"] = index
        pipeline_state["stages"][index]["status"] = status


def run_pipeline(file_paths: list[str], instructions: str):
    """
    Simula o pipeline do main.py com delays realistas.
    Substitua cada bloco pelo import e chamada real quando o backend estiver pronto.
    """
    try:
        with pipeline_lock:
            pipeline_state["status"] = "running"
            pipeline_state["instructions"] = instructions

        stages_work = [
            ("Extração de PDF",    2.5),
            ("Carregamento Base",  1.5),
            ("Embeddings",         3.0),
            ("Índice FAISS",       1.0),
            ("Setup Gemini",       0.5),
            ("Geração Markdown",   4.0),
            ("PDF da Apostila",    3.0),
            ("Geração de Vídeo",   2.0),
        ]

        for i, (name, duration) in enumerate(stages_work):
            set_stage(i, "running")
            time.sleep(duration)  # ← substitua pelo código real de cada etapa

            # Etapa 6 (PDF da Apostila): cria um PDF placeholder se não existir nenhum
            if i == 6:
                _ensure_placeholder_apostila(file_paths)

            set_stage(i, "done")

        # Pipeline completo → pausa para aprovação
        with pipeline_lock:
            pipeline_state["status"] = "awaiting_approval"

    except Exception as e:
        with pipeline_lock:
            pipeline_state["status"] = "error"
            pipeline_state["error"]  = str(e)
        # Marca etapa atual como error
        idx = pipeline_state["stage"]
        if 0 <= idx < len(STAGE_NAMES):
            pipeline_state["stages"][idx]["status"] = "error"


def _ensure_placeholder_apostila(file_paths: list[str]):
    """
    Cria um PDF de placeholder para teste caso o pipeline real não esteja integrado.
    Na versão real, o gerar_apostilas_por_curso() já salva em DATA_PDF.
    """
    # Usa o nome do primeiro PDF enviado como base do curso
    if not file_paths:
        return

    nome_base = Path(file_paths[0]).stem
    curso_dir = DATA_PDF / nome_base
    curso_dir.mkdir(parents=True, exist_ok=True)
    apostila_path = curso_dir / f"apostila_{nome_base}.pdf"

    if not apostila_path.exists():
        # Cria um PDF mínimo válido (1 página em branco) para testes de download
        try:
            from reportlab.pdfgen import canvas as rl_canvas
            c = rl_canvas.Canvas(str(apostila_path))
            c.setFont("Helvetica-Bold", 16)
            c.drawString(72, 750, f"Apostila — {nome_base}")
            c.setFont("Helvetica", 12)
            c.drawString(72, 720, "Gerada automaticamente pelo pipeline San Marino.")
            c.save()
        except ImportError:
            # reportlab não instalado: salva arquivo de texto como fallback
            apostila_path.with_suffix(".txt").write_text(
                f"Apostila placeholder para {nome_base}"
            )

    with pipeline_lock:
        pipeline_state["last_apostila"] = str(apostila_path)


# ---------------------------------------------------------------------------
# ── ROTAS PRINCIPAIS (consumidas por Index.tsx / api.ts) ──────────────────
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload_pdfs(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    instructions: str = Form(""),
    suggestions: str = Form(""),
):
    """
    Recebe um ou mais PDFs, salva em data/input/ e dispara o pipeline.
    O campo 'instructions' vem do UploadStep (caixa de alterações).
    O campo 'suggestions' é opcional e injetado no prompt de geração.
    """
    if not files:
        raise HTTPException(400, "Nenhum arquivo enviado.")

    reset_pipeline()
    saved_paths = []

    for upload in files:
        if not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"Arquivo '{upload.filename}' não é um PDF.")

        dest = DATA_INPUT / upload.filename
        content = await upload.read()
        dest.write_bytes(content)
        saved_paths.append(str(dest))

    with pipeline_lock:
        pipeline_state["uploaded_files"] = [Path(p).name for p in saved_paths]

    effective_instructions = instructions
    if suggestions:
        effective_instructions += f"\n\nSugestões de alteração do usuário: {suggestions}"

    thread = threading.Thread(
        target=run_pipeline,
        args=(saved_paths, effective_instructions),
        daemon=True,
    )
    thread.start()

    return {"ok": True, "files": [Path(p).name for p in saved_paths]}


@app.get("/status")
async def get_status():
    """
    Retorna o estado atual do pipeline.
    Consumido pelo ProcessingStep a cada 3 segundos.
    """
    with pipeline_lock:
        return {
            "status": pipeline_state["status"],
            "stage":  pipeline_state["stage"],
            "stages": pipeline_state["stages"],
            "error":  pipeline_state["error"],
        }


@app.get("/download/apostila")
async def download_apostila():
    """
    Baixa a apostila mais recente gerada pelo pipeline.
    Consumido pelo ApprovalStep após aprovação de conteúdo.
    """
    with pipeline_lock:
        apostila = pipeline_state.get("last_apostila")

    # Fallback: pega o primeiro PDF encontrado em data/output/workbooks_pdf/
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


@app.post("/approve")
async def approve_content():
    """
    Aprova o conteúdo gerado e avança o pipeline para geração de vídeo.
    Consumido pelo ApprovalStep.
    """
    with pipeline_lock:
        if pipeline_state["status"] not in ("awaiting_approval", "done"):
            raise HTTPException(400, "Pipeline não está aguardando aprovação.")
        pipeline_state["status"] = "done"

    return {"ok": True, "message": "Conteúdo aprovado."}


@app.post("/reject")
async def reject_content():
    """
    Rejeita o conteúdo e reseta o pipeline para o início.
    Consumido pelo ApprovalStep.
    """
    reset_pipeline()
    return {"ok": True, "message": "Pipeline resetado."}


@app.post("/approve/script")
async def approve_script():
    """
    Aprova os roteiros gerados e confirma a geração de vídeo.
    Consumido pelo ScriptApprovalStep (api.ts: approveScript).
    """
    with pipeline_lock:
        if pipeline_state["status"] not in ("done", "awaiting_approval"):
            raise HTTPException(400, "Pipeline não está em estado de aprovação de roteiro.")
    return {"ok": True, "message": "Roteiros aprovados."}


@app.post("/reject/script")
async def reject_script():
    """
    Rejeita os roteiros e reseta o pipeline.
    Consumido pelo ScriptApprovalStep (api.ts: rejectScript).
    """
    reset_pipeline()
    return {"ok": True, "message": "Roteiros rejeitados. Pipeline resetado."}


class RedoBody(BaseModel):
    suggestions: str = ""


@app.post("/redo")
async def redo_pipeline(body: RedoBody):
    """
    Re-executa o pipeline com os arquivos já salvos em disco e sugestões do usuário.
    Consumido pelo ApprovalStep ao clicar em 'Refazer com sugestões'.
    """
    with pipeline_lock:
        saved_names = list(pipeline_state.get("uploaded_files", []))

    if not saved_names:
        raise HTTPException(400, "Nenhum arquivo encontrado. Faça upload novamente.")

    file_paths = [str(DATA_INPUT / name) for name in saved_names]
    existing = [p for p in file_paths if Path(p).exists()]

    if not existing:
        raise HTTPException(400, "Arquivos originais não encontrados. Faça upload novamente.")

    effective_instructions = ""
    if body.suggestions:
        effective_instructions = f"\n\nSugestões de alteração do usuário: {body.suggestions}"

    reset_pipeline()
    with pipeline_lock:
        pipeline_state["uploaded_files"] = saved_names  # restaura após reset

    thread = threading.Thread(
        target=run_pipeline,
        args=(existing, effective_instructions),
        daemon=True,
    )
    thread.start()

    return {"ok": True}


@app.get("/videos")
async def list_videos():
    """
    Lista os vídeos disponíveis em data/output/videos/.
    Consumido pelo VideoStep.
    """
    videos = [
        f.name for f in DATA_VIDEO.iterdir()
        if f.is_file() and f.suffix.lower() in (".mp4", ".mov", ".avi", ".webm")
    ]
    return {"videos": sorted(videos)}


@app.get("/download/video/{nome}")
async def download_video(nome: str):
    """
    Baixa um vídeo específico por nome de arquivo.
    """
    path = DATA_VIDEO / nome
    if not path.exists():
        raise HTTPException(404, f"Vídeo '{nome}' não encontrado.")
    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


# ---------------------------------------------------------------------------
# ── ROTAS DO DASHBOARD (consumidas por CourseDashboard.tsx) ──────────────
# ---------------------------------------------------------------------------

@app.get("/cursos")
async def list_cursos():
    """
    Lê as pastas em data/output/workbooks_pdf/ e retorna os cursos com apostilas.
    Estrutura esperada:
      data/output/workbooks_pdf/
        └── Nome do Curso/
              └── apostila_nome_do_curso.pdf
    """
    cursos = []

    if not DATA_PDF.exists():
        return {"cursos": []}

    for entry in sorted(DATA_PDF.iterdir()):
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

        cursos.append({
            "nome":      entry.name,
            "pasta":     entry.name,
            "apostilas": apostilas,
        })

    return {"cursos": cursos}


@app.get("/download/apostila/{nome_arquivo}")
async def download_apostila_por_nome(nome_arquivo: str):
    """
    Baixa uma apostila específica buscando recursivamente em workbooks_pdf/.
    Consumido pelo CourseDashboard ao clicar no botão de download de cada apostila.
    """
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
# ── ROTAS DO GERADOR DE VÍDEOS (consumidas por GeradorVideos.tsx) ─────────
# ---------------------------------------------------------------------------

# Estado dos jobs do gerador de vídeos (job_id → Job)
video_jobs: dict[str, dict] = {}
video_jobs_lock = threading.Lock()


class ApproveMarkdownBody(BaseModel):
    markdown: str

class ApproveRoteiroBody(BaseModel):
    script: str

class AprovaCenasBody(BaseModel):
    scenes: list


def run_video_job(job_id: str, file_path: str):
    """
    Simula o pipeline do GeradorVideos com delays por etapa.
    Substitua pelos imports reais quando o backend estiver pronto.
    """
    def update(patch: dict):
        with video_jobs_lock:
            video_jobs[job_id].update(patch)

    try:
        # 1. Extração de markdown
        update({"state": "extracting"})
        time.sleep(3)

        # Lê o PDF enviado e gera um markdown placeholder
        nome_base = Path(file_path).stem
        markdown_placeholder = f"""# {nome_base}

## Ementa
Conteúdo extraído automaticamente do PDF pelo pipeline San Marino.

## Módulo 1 — Fundamentos
- Conceitos básicos
- Terminologia técnica
- Aplicações práticas

## Módulo 2 — Desenvolvimento
- Aprofundamento teórico
- Estudos de caso
- Exercícios propostos

## Módulo 3 — Conclusão
- Revisão dos conteúdos
- Avaliação formativa
- Material complementar
"""
        update({
            "state":       "awaiting_md_approval",
            "disciplina":  nome_base,
            "markdown":    markdown_placeholder,
        })

    except Exception as e:
        update({"state": "error", "erro": str(e)})


def run_video_job_after_markdown(job_id: str, markdown: str):
    def update(patch: dict):
        with video_jobs_lock:
            video_jobs[job_id].update(patch)

    try:
        update({"state": "generating_script"})
        time.sleep(4)

        disciplina = video_jobs[job_id].get("disciplina", "Disciplina")
        script = f"""# Roteiro — {disciplina}

Olá! Bem-vindos a mais uma aula da Escola Técnica San Marino.

Hoje vamos estudar {disciplina}, um conteúdo fundamental para a sua formação.

{markdown[:300]}...

Lembre-se: dedique-se aos estudos e consulte sempre o material de apoio.
Até a próxima aula!"""

        update({"state": "awaiting_script_approval", "script": script})

    except Exception as e:
        update({"state": "error", "erro": str(e)})


def run_video_job_after_script(job_id: str, script: str):
    def update(patch: dict):
        with video_jobs_lock:
            video_jobs[job_id].update(patch)

    try:
        update({"state": "generating_scenes"})
        time.sleep(3)

        disciplina = video_jobs[job_id].get("disciplina", "Disciplina")
        scenes = [
            {
                "disciplina": disciplina,
                "cenas": [
                    {
                        "numero": 1,
                        "nome": "Abertura",
                        "producao": "Tela com logo San Marino ao fundo",
                        "angulo": "Plano médio, câmera frontal",
                        "texto_na_tela": f"Bem-vindos — {disciplina}",
                        "fala": f"Olá! Bem-vindos à aula de {disciplina}.",
                    },
                    {
                        "numero": 2,
                        "nome": "Desenvolvimento",
                        "producao": "Slide com tópicos principais",
                        "angulo": "Close no avatar",
                        "texto_na_tela": "Conteúdo Principal",
                        "fala": script[:200] + "...",
                    },
                    {
                        "numero": 3,
                        "nome": "Encerramento",
                        "producao": "Tela de encerramento com logo",
                        "angulo": "Plano médio",
                        "texto_na_tela": "Até a próxima!",
                        "fala": "Isso é tudo por hoje. Até a próxima aula!",
                    },
                ],
            }
        ]

        update({"state": "awaiting_scenes_approval", "scenes": scenes})

    except Exception as e:
        update({"state": "error", "erro": str(e)})


def run_video_generation(job_id: str, scenes: list):
    def update(patch: dict):
        with video_jobs_lock:
            video_jobs[job_id].update(patch)

    try:
        update({"state": "generating_video"})
        time.sleep(5)  # Simula tempo de geração no HeyGen

        # Resultado simulado
        disciplina = video_jobs[job_id].get("disciplina", "Disciplina")
        update({
            "state": "completed",
            "videos": [
                {
                    "disciplina": disciplina,
                    "duration":   47.3,
                    "video_url":  None,  # URL real viria do HeyGen
                }
            ],
        })

    except Exception as e:
        update({"state": "error", "erro": str(e)})


@app.post("/gerador-videos/iniciar")
async def gerador_videos_iniciar(file: UploadFile = File(...)):
    """Inicia um job de geração de vídeo a partir de um PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF são aceitos.")

    job_id = str(uuid.uuid4())
    dest   = DATA_INPUT / f"gv_{job_id}_{file.filename}"
    content = await file.read()
    dest.write_bytes(content)

    with video_jobs_lock:
        video_jobs[job_id] = {"job_id": job_id, "state": "extracting"}

    thread = threading.Thread(
        target=run_video_job,
        args=(job_id, str(dest)),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/gerador-videos/status/{job_id}")
async def gerador_videos_status(job_id: str):
    """Retorna o estado atual de um job."""
    with video_jobs_lock:
        job = video_jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' não encontrado.")
    return job


@app.post("/gerador-videos/aprovar-markdown/{job_id}")
async def aprovar_markdown(job_id: str, body: ApproveMarkdownBody):
    """Aprova o markdown extraído e dispara geração do roteiro."""
    with video_jobs_lock:
        if job_id not in video_jobs:
            raise HTTPException(404, "Job não encontrado.")
        video_jobs[job_id]["markdown"] = body.markdown

    thread = threading.Thread(
        target=run_video_job_after_markdown,
        args=(job_id, body.markdown),
        daemon=True,
    )
    thread.start()
    return {"ok": True}


@app.post("/gerador-videos/aprovar-roteiro/{job_id}")
async def aprovar_roteiro(job_id: str, body: ApproveRoteiroBody):
    """Aprova o roteiro e dispara geração das cenas."""
    with video_jobs_lock:
        if job_id not in video_jobs:
            raise HTTPException(404, "Job não encontrado.")
        video_jobs[job_id]["script"] = body.script

    thread = threading.Thread(
        target=run_video_job_after_script,
        args=(job_id, body.script),
        daemon=True,
    )
    thread.start()
    return {"ok": True}


@app.post("/gerador-videos/aprovar-cenas/{job_id}")
async def aprovar_cenas(job_id: str, body: AprovaCenasBody):
    """Aprova as cenas e dispara a geração do vídeo."""
    with video_jobs_lock:
        if job_id not in video_jobs:
            raise HTTPException(404, "Job não encontrado.")
        video_jobs[job_id]["scenes"] = body.scenes

    thread = threading.Thread(
        target=run_video_generation,
        args=(job_id, body.scenes),
        daemon=True,
    )
    thread.start()
    return {"ok": True}


# ---------------------------------------------------------------------------
# ── HEALTH CHECK ──────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "San Marino Booklet Creator API",
        "version": "1.0.0",
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
        ],
    }


# ---------------------------------------------------------------------------
# ── ENTRYPOINT ───────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)