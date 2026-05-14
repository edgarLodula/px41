"""
Teste de Endpoints da API — ATRIA San Marino
Verifica se cada rota responde corretamente com a API em execução.

Pré-requisito: API rodando em http://localhost:8000
Execute com: python scripts/teste_endpoints_api.py
"""

import sys
import os
import requests

BASE_URL = "http://localhost:8000"

VERDE  = "\033[92m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
RESET  = "\033[0m"
NEGRITO = "\033[1m"

resultados = []

def ok(label, detalhe=""):
    msg = f"  {VERDE}✔ OK{RESET}  — {label}"
    if detalhe:
        msg += f"  ({detalhe})"
    print(msg)
    resultados.append(("OK", label))

def aviso(label, detalhe=""):
    msg = f"  {AMARELO}⚠ AVISO{RESET} — {label}"
    if detalhe:
        msg += f"  ({detalhe})"
    print(msg)
    resultados.append(("AVISO", label))

def erro(label, detalhe=""):
    msg = f"  {VERMELHO}✘ ERRO{RESET}  — {label}"
    if detalhe:
        msg += f"  ({detalhe})"
    print(msg)
    resultados.append(("ERRO", label))


def verificar_servidor_ativo():
    """Confirma que a API está rodando antes de executar os testes."""
    print(f"\n{NEGRITO}[0] Verificando conexão com a API em {BASE_URL}...{RESET}")
    try:
        r = requests.get(f"{BASE_URL}/status", timeout=5)
        ok("Servidor acessível", f"HTTP {r.status_code}")
        return True
    except requests.ConnectionError:
        erro("Servidor inacessível", f"Certifique-se de que a API está rodando: uvicorn api:app --host 127.0.0.1 --port 8000")
        return False


def testar_docs_e_openapi():
    """GET /docs e /openapi.json devem retornar HTTP 200."""
    print(f"\n{NEGRITO}[1] Documentação automática (Swagger / OpenAPI)...{RESET}")

    r = requests.get(f"{BASE_URL}/docs")
    if r.status_code == 200:
        ok("GET /docs", "Swagger UI disponível")
    else:
        erro("GET /docs", f"HTTP {r.status_code}")

    r = requests.get(f"{BASE_URL}/openapi.json")
    if r.status_code == 200:
        schema = r.json()
        rotas = list(schema.get("paths", {}).keys())
        ok("GET /openapi.json", f"{len(rotas)} rota(s) no schema: {', '.join(rotas)}")
    else:
        erro("GET /openapi.json", f"HTTP {r.status_code}")


def testar_status_inicial():
    """GET /status deve retornar status 'idle' antes de qualquer upload."""
    print(f"\n{NEGRITO}[2] Status inicial do pipeline...{RESET}")

    r = requests.get(f"{BASE_URL}/status")
    if r.status_code != 200:
        erro("GET /status", f"HTTP {r.status_code}")
        return

    data = r.json()
    campos_esperados = ["status", "stage", "stages", "error", "videos"]
    campos_ausentes = [c for c in campos_esperados if c not in data]

    if campos_ausentes:
        aviso("GET /status — campos ausentes no JSON", str(campos_ausentes))
    else:
        ok("GET /status — todos os campos presentes", str(campos_esperados))

    status_atual = data.get("status")
    if status_atual == "idle":
        ok("Status inicial correto", "'idle'")
    else:
        aviso("Status não é 'idle'", f"atual: '{status_atual}'")

    total_stages = len(data.get("stages", []))
    if total_stages == 8:
        ok("Etapas do pipeline", f"{total_stages} etapas registradas")
    else:
        aviso("Número inesperado de etapas", f"esperado: 8, encontrado: {total_stages}")


def testar_approve_sem_pipeline_ativo():
    """POST /approve deve rejeitar se o pipeline não estiver aguardando aprovação."""
    print(f"\n{NEGRITO}[3] Aprovação sem pipeline ativo...{RESET}")

    r = requests.post(f"{BASE_URL}/approve")
    if r.status_code == 400:
        ok("POST /approve retorna 400 corretamente", "pipeline não está aguardando aprovação")
    else:
        aviso("POST /approve", f"esperado HTTP 400, recebido HTTP {r.status_code}")


def testar_reject():
    """POST /reject deve resetar o pipeline e retornar mensagem."""
    print(f"\n{NEGRITO}[4] Reset do pipeline via /reject...{RESET}")

    r = requests.post(f"{BASE_URL}/reject")
    if r.status_code == 200 and "message" in r.json():
        ok("POST /reject", r.json()["message"])
    else:
        erro("POST /reject", f"HTTP {r.status_code} — {r.text[:100]}")


def testar_download_apostila_sem_arquivo():
    """GET /download/apostila deve retornar 404 se nenhuma apostila foi gerada."""
    print(f"\n{NEGRITO}[5] Download de apostila sem arquivo gerado...{RESET}")

    r = requests.get(f"{BASE_URL}/download/apostila")
    if r.status_code == 404:
        ok("GET /download/apostila retorna 404 corretamente", "nenhuma apostila no estado atual")
    else:
        aviso("GET /download/apostila", f"esperado HTTP 404, recebido HTTP {r.status_code}")


def testar_download_videos_sem_arquivo():
    """GET /download/videos deve retornar 404 se nenhum vídeo foi gerado."""
    print(f"\n{NEGRITO}[6] Listagem de vídeos sem arquivos gerados...{RESET}")

    r = requests.get(f"{BASE_URL}/download/videos")
    if r.status_code == 404:
        ok("GET /download/videos retorna 404 corretamente", "nenhum vídeo no estado atual")
    else:
        aviso("GET /download/videos", f"esperado HTTP 404, recebido HTTP {r.status_code}")


def testar_download_video_por_nome_inexistente():
    """GET /download/video/{nome} deve retornar 404 para disciplina inexistente."""
    print(f"\n{NEGRITO}[7] Download de vídeo por nome inexistente...{RESET}")

    r = requests.get(f"{BASE_URL}/download/video/disciplina_que_nao_existe")
    if r.status_code == 404:
        ok("GET /download/video/{nome} retorna 404 corretamente", "disciplina não encontrada")
    else:
        aviso("GET /download/video/{nome}", f"esperado HTTP 404, recebido HTTP {r.status_code}")


def testar_upload_sem_arquivo():
    """POST /upload sem arquivo deve retornar erro de validação (422)."""
    print(f"\n{NEGRITO}[8] Upload sem arquivo...{RESET}")

    r = requests.post(f"{BASE_URL}/upload")
    if r.status_code == 422:
        ok("POST /upload sem arquivo retorna 422 corretamente", "validação de campo obrigatório")
    else:
        aviso("POST /upload", f"esperado HTTP 422, recebido HTTP {r.status_code}")


def testar_upload_com_pdf_falso():
    """POST /upload com um PDF mínimo válido deve iniciar o pipeline."""
    print(f"\n{NEGRITO}[9] Upload de PDF de teste...{RESET}")

    pdf_minimo = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"

    arquivos = {"files": ("teste_diagnostico.pdf", pdf_minimo, "application/pdf")}
    r = requests.post(f"{BASE_URL}/upload", files=arquivos)

    if r.status_code == 200:
        ok("POST /upload com PDF", r.json().get("message", "pipeline iniciado"))

        # Aguarda brevemente e verifica se o status mudou
        import time
        time.sleep(2)
        r2 = requests.get(f"{BASE_URL}/status")
        status = r2.json().get("status")
        if status in ("running", "error", "awaiting_approval", "done"):
            ok("Pipeline disparado", f"status: '{status}'")
        else:
            aviso("Status após upload inesperado", f"'{status}'")

        # Reseta após o teste
        requests.post(f"{BASE_URL}/reject")
        ok("Pipeline resetado após teste")
    else:
        erro("POST /upload com PDF", f"HTTP {r.status_code} — {r.text[:200]}")


# =============================================================
# EXECUÇÃO
# =============================================================
if __name__ == "__main__":
    print(f"\n{NEGRITO}{'=' * 60}")
    print("TESTE DE ENDPOINTS — ATRIA San Marino API")
    print(f"{'=' * 60}{RESET}")

    if not verificar_servidor_ativo():
        sys.exit(1)

    testar_docs_e_openapi()
    testar_status_inicial()
    testar_approve_sem_pipeline_ativo()
    testar_reject()
    testar_download_apostila_sem_arquivo()
    testar_download_videos_sem_arquivo()
    testar_download_video_por_nome_inexistente()
    testar_upload_sem_arquivo()
    testar_upload_com_pdf_falso()

    # Resumo final
    total   = len(resultados)
    n_ok    = sum(1 for r, _ in resultados if r == "OK")
    n_aviso = sum(1 for r, _ in resultados if r == "AVISO")
    n_erro  = sum(1 for r, _ in resultados if r == "ERRO")

    print(f"\n{NEGRITO}{'=' * 60}")
    print("RESUMO FINAL")
    print(f"{'=' * 60}{RESET}")
    print(f"  Total de verificações : {total}")
    print(f"  {VERDE}✔ OK     : {n_ok}{RESET}")
    print(f"  {AMARELO}⚠ Avisos : {n_aviso}{RESET}")
    print(f"  {VERMELHO}✘ Erros  : {n_erro}{RESET}")
    print()

    sys.exit(0 if n_erro == 0 else 1)
