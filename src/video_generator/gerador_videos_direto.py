"""
Gerador de Vídeos Direto — máquina de estados com aprovação por etapa.

Fluxo:
  PDF → [extração] → ✅ Aprovação Markdown
      → [geração roteiro] → ✅ Aprovação Roteiro
      → [geração cenas]   → ✅ Aprovação Cenas
      → [geração vídeo]   → ✅ Vídeo pronto

Em cada etapa de aprovação, o usuário pode editar o conteúdo gerado antes de avançar.

LIMITES (remova ou ajuste conforme necessário):
  LIMITE_DISCIPLINAS  = 1   → processa apenas 1 disciplina por PDF
  LIMITE_PALAVRAS_MD  = 800 → caracteres do markdown enviados ao Gemini para roteiro
  LIMITE_PALAVRAS     = 80  → palavras no roteiro final (~37 segundos de vídeo)
"""

import os
import re
import time
import uuid
import requests
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

# ─── LIMITES REMOVÍVEIS ────────────────────────────────────────────────────────
LIMITE_DISCIPLINAS  = 1     # disciplinas processadas por PDF
LIMITE_PALAVRAS     = 80    # palavras máximas no roteiro final
LIMITE_PALAVRAS_MD  = 1200  # chars do markdown usados como contexto para o Gemini
# ──────────────────────────────────────────────────────────────────────────────

HEYGEN_BASE_URL     = "https://api.heygen.com"
HEYGEN_ASPECT_RATIO = "16:9"
HEYGEN_ENGINE       = "avatar_iv"
GEMINI_MODEL        = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Estados possíveis do job
ESTADOS = [
    "extracting",              # 1. Extraindo disciplina do PDF
    "awaiting_md_approval",    # 2. ✅ Usuário revisa e aprova o Markdown
    "generating_script",       # 3. Gemini gera o roteiro
    "awaiting_script_approval",# 4. ✅ Usuário revisa e aprova o roteiro
    "generating_scenes",       # 5. Gemini gera o plano de cenas
    "awaiting_scenes_approval",# 6. ✅ Usuário revisa e aprova as cenas
    "generating_video",        # 7. HeyGen renderiza o vídeo
    "completed",               # 8. ✅ Vídeo pronto
    "error",
]


# =============================================================================
# ESTRUTURA DO JOB
# =============================================================================

def novo_job() -> dict:
    return {
        "job_id":    str(uuid.uuid4()),
        "state":     "extracting",
        "disciplina": None,
        "ementa":    None,
        # conteúdo gerado em cada etapa (pode ser editado pelo usuário)
        "markdown":  None,
        "script":    None,
        "scenes":    None,
        # resultado final
        "video_id":  None,
        "video_url": None,
        "duration":  None,
        "erro":      None,
        "limites": {
            "disciplinas":      LIMITE_DISCIPLINAS,
            "palavras_roteiro": LIMITE_PALAVRAS,
        },
    }


# =============================================================================
# ETAPA 1 — EXTRAÇÃO DO PDF → MARKDOWN
# =============================================================================

def extrair_markdown_do_pdf(caminho_pdf: str) -> dict:
    """
    Extrai a primeira disciplina do PDF e converte para Markdown estruturado.
    Retorna dict com 'disciplina', 'ementa', 'markdown'.
    """
    registros = _extrair_tabelas(caminho_pdf) or _extrair_por_texto(caminho_pdf)

    if not registros:
        raise ValueError("Nenhuma disciplina encontrada no PDF.")

    item = registros[0]
    disciplina = item["disciplina"]
    ementa     = item["ementa"]
    conteudo   = item["conteudo"]

    markdown = f"# {disciplina}\n\n"
    if ementa:
        markdown += f"## Ementa\n\n{ementa}\n\n"
    if conteudo:
        markdown += f"## Conteúdo Programático\n\n{conteudo}\n\n"

    return {"disciplina": disciplina, "ementa": ementa, "markdown": markdown.strip()}


def _extrair_tabelas(caminho_pdf: str) -> list[dict]:
    registros = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            for tabela in (pagina.extract_tables() or []):
                for linha in tabela:
                    if not linha or not linha[0]:
                        continue
                    celula0 = str(linha[0]).strip()
                    if celula0.lower() in ("", "disciplina", "módulo", "matéria"):
                        continue
                    registros.append({
                        "disciplina": celula0,
                        "ementa":     str(linha[1]).strip() if len(linha) > 1 and linha[1] else "",
                        "conteudo":   str(linha[2]).strip() if len(linha) > 2 and linha[2] else "",
                    })
                    if len(registros) >= LIMITE_DISCIPLINAS:
                        return registros
    return registros


def _extrair_por_texto(caminho_pdf: str) -> list[dict]:
    registros = []
    with pdfplumber.open(caminho_pdf) as pdf:
        texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
    for linha in texto.splitlines():
        linha = linha.strip()
        if len(linha) > 10 and not linha[0].isdigit():
            registros.append({"disciplina": linha, "ementa": "", "conteudo": ""})
            if len(registros) >= LIMITE_DISCIPLINAS:
                break
    return registros


# =============================================================================
# ETAPA 2 — MARKDOWN APROVADO → ROTEIRO
# =============================================================================

def gerar_roteiro(markdown: str, disciplina: str, gemini_token: str) -> str:
    """
    Recebe o Markdown aprovado e gera um roteiro de vídeo-aula inaugural.
    Truncado a LIMITE_PALAVRAS palavras.
    """
    contexto = markdown[:LIMITE_PALAVRAS_MD]

    prompt = f"""Você é um roteirista especialista em vídeo-aulas técnicas de saúde.

Com base no conteúdo abaixo da disciplina "{disciplina}", escreva APENAS o texto que o avatar deve falar em um vídeo de abertura.

REGRAS OBRIGATÓRIAS:
- Escreva SOMENTE a fala do avatar, sem títulos, marcações, colchetes ou símbolos
- Máximo de {LIMITE_PALAVRAS} palavras
- Tom: acolhedor, confiante, direto
- Mencione a Escola Técnica San Marino
- Apresente a disciplina e faça uma promessa de valor ao aluno
- Termine com uma frase de boas-vindas motivadora

CONTEÚDO DA DISCIPLINA:
{contexto}

Escreva apenas o texto da fala:"""

    return _chamar_gemini(prompt, gemini_token, max_tokens=400)


def _truncar_palavras(texto: str, n: int) -> str:
    palavras = texto.split()
    return texto if len(palavras) <= n else " ".join(palavras[:n]) + "."


# =============================================================================
# ETAPA 3 — ROTEIRO APROVADO → PLANO DE CENAS
# =============================================================================

def gerar_plano_cenas(roteiro: str, disciplina: str, gemini_token: str) -> str:
    """
    Recebe o roteiro aprovado e gera um plano visual de cenas detalhado.
    O usuário pode editar antes de avançar para o HeyGen.
    """
    prompt = f"""Você é um diretor criativo de vídeo-aulas.

Com base no roteiro abaixo para a disciplina "{disciplina}", crie um PLANO DE CENAS detalhado.

ROTEIRO:
{roteiro}

FORMATO DO PLANO DE CENAS (siga exatamente):
---
CENA 1 — [Nome da cena] ([tempo aproximado, ex: 0:00 - 0:08])
[AVATAR] Emoção/postura do avatar (ex: Sorrindo, olhar confiante, mãos abertas)
[FALA] Trecho exato do roteiro para esta cena
[TEXTO NA TELA] Palavras-chave ou frase de impacto (máx. 6 palavras)
[VISUAL/FUNDO] Descrição do cenário ou fundo sugerido

CENA 2 — ...
---

Crie entre 3 e 5 cenas cobrindo todo o roteiro. Seja específico e visual."""

    return _chamar_gemini(prompt, gemini_token, max_tokens=800)


# =============================================================================
# ETAPA 4 — CENAS APROVADAS → VÍDEO (HEYGEN v3)
# =============================================================================

def gerar_video_heygen(
    roteiro:      str,
    disciplina:   str,
    heygen_token: str,
    avatar_id:    str | None = None,
    voice_id:     str | None = None,
) -> str:
    """
    Envia o roteiro aprovado para HeyGen v3 e retorna o video_id.
    """
    avatar_id = avatar_id or os.getenv("HEYGEN_AVATAR_ID")
    voice_id  = voice_id  or os.getenv("HEYGEN_VOICE_ID")

    if not avatar_id:
        raise ValueError("HEYGEN_AVATAR_ID não configurado.")
    if not voice_id:
        raise ValueError("HEYGEN_VOICE_ID não configurado.")

    headers = {
        "X-Api-Key":      heygen_token,
        "Content-Type":   "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }

    payload = {
        "type":         "avatar",
        "avatar_id":    avatar_id,
        "voice_id":     voice_id,
        "script":       _truncar_palavras(roteiro, LIMITE_PALAVRAS),
        "title":        f"Introdução — {disciplina}",
        "aspect_ratio": HEYGEN_ASPECT_RATIO,
        "engine":       {"type": HEYGEN_ENGINE},
        "voice_settings": {"speed": 1.0},
    }

    resp = requests.post(
        f"{HEYGEN_BASE_URL}/v3/videos",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if not resp.ok:
        raise RuntimeError(
            f"HeyGen /v3/videos falhou: HTTP {resp.status_code} — {resp.text[:300]}"
        )

    data     = resp.json().get("data", {})
    video_id = data.get("video_id")
    if not video_id:
        raise RuntimeError(f"HeyGen não retornou video_id: {resp.text[:300]}")

    return video_id


def verificar_status_video(video_id: str, heygen_token: str) -> dict:
    """Consulta o status de um vídeo no HeyGen v3."""
    resp = requests.get(
        f"{HEYGEN_BASE_URL}/v3/videos/{video_id}",
        headers={"X-Api-Key": heygen_token},
        timeout=15,
    )
    if not resp.ok:
        raise RuntimeError(f"GET /v3/videos/{video_id}: HTTP {resp.status_code}")

    data = resp.json().get("data", {})
    return {
        "status":        data.get("status", "unknown"),
        "video_url":     data.get("video_url"),
        "thumbnail_url": data.get("thumbnail_url"),
        "duration":      data.get("duration"),
        "error":         data.get("error"),
    }


def aguardar_video(video_id: str, heygen_token: str, max_min: int = 10) -> dict:
    """Polling até completed/failed. Aguarda até max_min minutos."""
    tentativas = (max_min * 60) // 10
    for _ in range(tentativas):
        info = verificar_status_video(video_id, heygen_token)
        if info["status"] == "completed":
            return info
        if info["status"] == "failed":
            raise RuntimeError(f"HeyGen falhou: {info.get('error')}")
        time.sleep(10)
    raise TimeoutError(f"Vídeo não ficou pronto em {max_min} minutos.")


# =============================================================================
# UTILITÁRIO GEMINI
# =============================================================================

def _chamar_gemini(prompt: str, token: str, max_tokens: int = 500) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
    }
    headers = {"Content-Type": "application/json"}

    for tentativa in range(3):
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}"
                f":generateContent?key={token}",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            if tentativa < 2:
                time.sleep(5 * (tentativa + 1))
            else:
                raise RuntimeError(f"Gemini falhou após 3 tentativas: {e}")
