"""
Gerador de Vídeos Direto — máquina de estados com aprovação por etapa.

Fluxo:
  PDF → [extração] → ✅ Aprovação Markdown
      → [geração roteiro] → ✅ Aprovação Roteiro
      → [geração cenas]   → ✅ Aprovação Cenas
      → [geração vídeo]   → ✅ Vídeo pronto

Em cada etapa de aprovação, o usuário pode editar o conteúdo gerado antes de avançar.
"""

import os
import re
import time
import uuid
import requests
import pdfplumber
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIGURAÇÕES DE PROCESSAMENTO ───────────────────────────────────────────
LIMITE_DISCIPLINAS  = None  # None = processa todas as disciplinas do PDF
LIMITE_PALAVRAS     = None  # None = sem limite de palavras no roteiro
LIMITE_PALAVRAS_MD  = None  # None = usa o markdown completo como contexto
# ──────────────────────────────────────────────────────────────────────────────

HEYGEN_BASE_URL       = "https://api.heygen.com"
HEYGEN_ASPECT_RATIO   = "16:9"
HEYGEN_ENGINE         = "avatar_iv"       # "avatar_iv" (padrão) | "avatar_v" (melhor qualidade)
HEYGEN_SPEED          = 1.0               # 0.5–2.0
HEYGEN_EXPRESSIVENESS = "medium"          # "low" | "medium" | "high"
HEYGEN_MOTION_PROMPT  = "calm, professional, occasional hand gestures while teaching"
HEYGEN_BG_ASSET_ID    = os.getenv("HEYGEN_BG_ASSET_ID", "")
HEYGEN_BG_COLOR       = "#1a2744"         # fallback: azul escuro neutro
OPENAI_MODEL          = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Estados possíveis do job
ESTADOS = [
    "extracting",               # 1. Extraindo disciplina do PDF
    "awaiting_md_approval",     # 2. ✅ Usuário revisa e aprova o Markdown
    "generating_script",        # 3. OpenAI gera o roteiro
    "awaiting_script_approval", # 4. ✅ Usuário revisa e aprova o roteiro
    "generating_scenes",        # 5. Parseia o plano de cenas
    "awaiting_scenes_approval", # 6. ✅ Usuário revisa e aprova as cenas
    "generating_video",         # 7. HeyGen renderiza o vídeo
    "completed",                # 8. ✅ Vídeo pronto
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
# ETAPA 1 — EXTRAÇÃO DO PDF → MARKDOWN (via OpenAI)
# =============================================================================

def extrair_markdown_do_pdf(caminho_pdf: str, openai_token: str = None) -> dict:
    """
    Extrai o texto bruto do PDF e usa a OpenAI para estruturar
    o conteúdo em Markdown por disciplina.

    Retorna dict com 'disciplina', 'ementa', 'markdown'.
    """
    texto_bruto = _extrair_texto_pdf(caminho_pdf)

    if not texto_bruto.strip():
        raise ValueError("Nenhum texto extraído do PDF. O arquivo pode ser uma imagem escaneada.")

    token = openai_token or os.getenv("OPENAI_API_KEY")
    if not token:
        raise ValueError("OPENAI_API_KEY não configurada.")

    markdown = _openai_estruturar_pdf(texto_bruto, token)

    disciplina = _extrair_nome_disciplina(markdown)

    return {
        "disciplina": disciplina,
        "ementa":     "",   # ementa está dentro do markdown
        "markdown":   markdown,
    }


def _extrair_texto_pdf(caminho_pdf: str) -> str:
    """Extrai todo o texto do PDF usando pdfplumber."""
    with pdfplumber.open(caminho_pdf) as pdf:
        paginas = [p.extract_text() or "" for p in pdf.pages]
    return "\n\n".join(paginas)


def _openai_estruturar_pdf(texto_bruto: str, token: str) -> str:
    """
    Envia o texto bruto do PDF para a OpenAI e pede para estruturar
    em Markdown limpo com todas as disciplinas.
    """
    contexto = texto_bruto[:12000]

    prompt = f"""Você é um especialista em organização de currículos educacionais.

O texto abaixo foi extraído de um PDF de currículo escolar.
Sua tarefa é transformar esse texto em Markdown bem estruturado, organizando as disciplinas.

REGRAS:
- Use `# Nome da Disciplina` para cada disciplina
- Use `## Ementa` para a ementa de cada disciplina
- Use `## Conteúdo Programático` para os conteúdos, com itens em lista (`- item`)
- Mantenha o conteúdo original fielmente — não invente informações
- Se houver várias disciplinas, inclua todas
- Ignore cabeçalhos institucionais (nome da escola, endereço, portaria, etc.)
- Retorne APENAS o Markdown, sem explicações adicionais

TEXTO DO PDF:
{contexto}

Markdown estruturado:"""

    return _chamar_openai(prompt, token, max_tokens=4000)


def _extrair_nome_disciplina(markdown: str) -> str:
    """Extrai o nome da primeira disciplina do markdown gerado."""
    for linha in markdown.splitlines():
        linha = linha.strip()
        if linha.startswith("# "):
            return linha[2:].strip()
    return "Disciplina"


# =============================================================================
# ETAPA 2 — MARKDOWN APROVADO → ROTEIROS DE PRODUÇÃO (um por disciplina)
# =============================================================================

def gerar_roteiro(markdown: str, disciplina: str, openai_token: str) -> str:
    """
    Recebe o Markdown completo aprovado e gera um roteiro de produção
    para CADA disciplina encontrada.

    O roteiro contém:
    - [FALA] — texto exato que o avatar vai falar
    - [PRODUCAO] — direção de expressão/postura do avatar
    - [ANGULO] — sugestão de enquadramento/ângulo de câmera
    - [TEXTO NA TELA] — texto sobreposto ao vídeo (caption/lower third)

    Retorna um documento único com todos os roteiros separados por disciplina.
    """
    contexto = markdown if not LIMITE_PALAVRAS_MD else markdown[:LIMITE_PALAVRAS_MD]

    prompt = f"""Você é um diretor criativo especialista em vídeo-aulas técnicas para cursos de saúde e administração.

Você recebeu o currículo completo abaixo. Sua tarefa é criar um ROTEIRO DE PRODUÇÃO para cada disciplina encontrada.

FORMATO OBRIGATÓRIO para cada disciplina:
---
DISCIPLINA: [nome completo da disciplina]
---

[CENA 1 — ABERTURA]
[PRODUCAO] Direção de expressão e postura do avatar (ex: "Sorrindo, olhar confiante para a câmera, tom acolhedor")
[ANGULO] Sugestão de enquadramento (ex: "Plano médio, avatar centralizado")
[TEXTO NA TELA] Texto curto para exibir na tela (máx. 6 palavras)
[FALA] Texto exato que o avatar vai falar nesta cena

[CENA 2 — DESENVOLVIMENTO]
[PRODUCAO] ...
[ANGULO] ...
[TEXTO NA TELA] ...
[FALA] ...

[CENA 3 — ENCERRAMENTO]
[PRODUCAO] ...
[ANGULO] ...
[TEXTO NA TELA] ...
[FALA] ...

---
DISCIPLINA: [próxima disciplina]
---
... (repete o formato)

REGRAS:
- Crie entre 3 e 5 cenas por disciplina
- [FALA] deve ser fluido, natural, sem marcações — é o texto exato para TTS
- [PRODUCAO] guia o avatar (expressividade, gestos, emoção)
- [ANGULO] é sugestão para edição posterior (não afeta o HeyGen diretamente)
- [TEXTO NA TELA] são palavras-chave impactantes para sobrepor no vídeo
- Tom geral: acolhedor, empolgante, profissional
- Mencione a Escola Técnica San Marino na abertura da primeira disciplina
- Cada disciplina deve ter sua identidade própria no roteiro

CURRÍCULO:
{contexto}

Gere os roteiros de produção:"""

    return _chamar_openai(prompt, openai_token, max_tokens=6000)


def extrair_falas_do_roteiro(roteiro_ou_cenas) -> dict[str, str]:
    """
    Extrai o texto de fala por disciplina.
    Aceita tanto o roteiro em texto (str) quanto a estrutura de cenas (list).
    Retorna dict { nome_disciplina: texto_fala_concatenado }
    """
    if isinstance(roteiro_ou_cenas, list):
        resultado = {}
        for disc in roteiro_ou_cenas:
            nome = disc.get("disciplina", "Disciplina")
            falas = [c["fala"] for c in disc.get("cenas", []) if c.get("fala")]
            if falas:
                resultado[nome] = " ".join(falas)
        return resultado

    # Fallback: parseia o texto do roteiro
    disciplinas: dict[str, str] = {}
    disciplina_atual = None
    falas: list[str] = []

    for linha in roteiro_ou_cenas.splitlines():
        ls = linha.strip()
        if ls.startswith("DISCIPLINA:"):
            if disciplina_atual and falas:
                disciplinas[disciplina_atual] = " ".join(falas).strip()
            disciplina_atual = ls.replace("DISCIPLINA:", "").strip().strip("-").strip()
            falas = []
        elif ls.startswith("[FALA]"):
            texto = ls.replace("[FALA]", "").strip()
            if texto:
                falas.append(texto)

    if disciplina_atual and falas:
        disciplinas[disciplina_atual] = " ".join(falas).strip()

    return disciplinas


def _truncar_palavras(texto: str, n: int) -> str:
    palavras = texto.split()
    return texto if len(palavras) <= n else " ".join(palavras[:n]) + "."


# =============================================================================
# ETAPA 3 — ROTEIRO APROVADO → PLANO DE CENAS
# =============================================================================

def parsear_cenas_do_roteiro(roteiro: str) -> list[dict]:
    """
    Parseia o roteiro aprovado e extrai a estrutura de cenas por disciplina.
    Sem chamada à API — usa o que o usuário já aprovou.

    Retorna lista de dicts:
    [
      {
        "disciplina": "Introdução à Administração",
        "cenas": [
          {
            "numero": 1,
            "nome": "Abertura",
            "producao": "Sorrindo, olhar confiante",
            "angulo": "Plano médio",
            "texto_na_tela": "Escola San Marino",
            "fala": "Olá! Seja bem-vindo..."
          },
          ...
        ]
      },
      ...
    ]
    """
    disciplinas = []
    disciplina_atual = None
    cenas_atuais: list[dict] = []
    cena_atual: dict | None = None

    def _salvar_cena():
        if cena_atual and cena_atual.get("fala"):
            cenas_atuais.append(dict(cena_atual))

    def _salvar_disciplina():
        nonlocal cena_atual
        _salvar_cena()
        if disciplina_atual and cenas_atuais:
            disciplinas.append({
                "disciplina": disciplina_atual,
                "cenas":      list(cenas_atuais),
            })

    for linha in roteiro.splitlines():
        ls = linha.strip()
        if not ls:
            continue

        # Nova disciplina
        if ls.startswith("DISCIPLINA:") or (ls.startswith("---") and "DISCIPLINA:" in roteiro[roteiro.find(ls):roteiro.find(ls)+50]):
            nome = ls.replace("DISCIPLINA:", "").strip().strip("-").strip()
            if nome:
                _salvar_disciplina()
                disciplina_atual = nome
                cenas_atuais.clear()
                cena_atual = None

        # Nova cena
        elif ls.upper().startswith("[CENA ") or (ls.upper().startswith("CENA ") and "—" in ls):
            _salvar_cena()
            nome_cena = ls.strip("[]").split("—", 1)[-1].strip() if "—" in ls else ls
            nome_cena = re.sub(r'\([\d:]+\s*-\s*[\d:]+\)', '', nome_cena).strip()
            numero = len(cenas_atuais) + 1
            cena_atual = {
                "numero":        numero,
                "nome":          nome_cena,
                "producao":      "",
                "angulo":        "",
                "texto_na_tela": "",
                "fala":          "",
            }

        elif cena_atual is not None:
            if ls.startswith("[PRODUCAO]") or ls.startswith("[PRODUCÃO]"):
                cena_atual["producao"] = ls.split("]", 1)[-1].strip()
            elif ls.startswith("[ANGULO]") or ls.startswith("[ÂNGULO]"):
                cena_atual["angulo"] = ls.split("]", 1)[-1].strip()
            elif ls.startswith("[TEXTO NA TELA]"):
                cena_atual["texto_na_tela"] = ls.split("]", 1)[-1].strip()
            elif ls.startswith("[FALA]"):
                cena_atual["fala"] = ls.replace("[FALA]", "").strip()
            elif cena_atual.get("fala") and not ls.startswith("["):
                cena_atual["fala"] += " " + ls

    _salvar_disciplina()
    return disciplinas


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
        "X-Api-Key":       heygen_token,
        "Content-Type":    "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }

    payload = {
        "type": "avatar",
        "avatar_id": avatar_id,
        "voice_id": voice_id,
        "script": roteiro if not LIMITE_PALAVRAS else _truncar_palavras(roteiro, LIMITE_PALAVRAS),
        "title": f"Introdução — {disciplina}",
        "aspect_ratio": HEYGEN_ASPECT_RATIO,
        "fit": "contain",
        "engine": {"type": HEYGEN_ENGINE},
        "voice_settings": {"speed": HEYGEN_SPEED},
        "expressiveness": HEYGEN_EXPRESSIVENESS,
        "motion_prompt": (
            "enthusiastic teacher, natural hand gestures, pointing at board, "
            "head nodding while explaining, occasional eyebrow raise "
            "for emphasis, calm and professional posture"
        ),
        "background": (
            {"type": "image", "asset_id": HEYGEN_BG_ASSET_ID}
            if HEYGEN_BG_ASSET_ID
            else {"type": "color", "value": HEYGEN_BG_COLOR}
        ),
        "caption": {"style": "default"},
    }

    debug_payload = {**payload, "script": f"[{len(payload['script'])} chars]"}
    print(f"[DEBUG] Payload enviado ao HeyGen: {debug_payload}")

    resp = requests.post(
        f"{HEYGEN_BASE_URL}/v3/videos",
        headers=headers,
        json=payload,
        timeout=30,
    )

    print(f"[DEBUG] HeyGen resposta HTTP {resp.status_code}: {resp.text[:500]}")

    if not resp.ok:
        raise RuntimeError(
            f"HeyGen /v3/videos falhou: HTTP {resp.status_code} — {resp.text[:300]}"
        )

    data     = resp.json().get("data", {})
    video_id = data.get("video_id")
    if not video_id:
        raise RuntimeError(f"HeyGen não retornou video_id: {resp.text[:300]}")

    print(f"[DEBUG] video_id recebido: {video_id}")
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


def aguardar_video(video_id: str, heygen_token: str, max_min: int = 1.0) -> dict:
    """Polling até completed/failed. Aguarda até max_min minutos."""
    tentativas = int((max_min * 60) // 10)
    for _ in range(tentativas):
        info = verificar_status_video(video_id, heygen_token)
        if info["status"] == "completed":
            return info
        if info["status"] == "failed":
            raise RuntimeError(f"HeyGen falhou. Resposta completa: {info}")
        time.sleep(10)
    raise TimeoutError(f"Vídeo não ficou pronto em {max_min} minutos.")


def _upload_slide_heygen(caminho_slide: str, heygen_token: str) -> str:
    """
    Faz upload de um slide PNG para o HeyGen e retorna o asset_id.
    Usado como background image em cada cena do vídeo.
    """
    nome_arquivo = os.path.basename(caminho_slide)
    with open(caminho_slide, "rb") as f:
        resp = requests.post(
            f"{HEYGEN_BASE_URL}/v3/assets",
            headers={"X-Api-Key": heygen_token},
            files={"file": (nome_arquivo, f, "image/png")},
            timeout=60,
        )
    if not resp.ok:
        raise RuntimeError(
            f"Upload slide falhou ({nome_arquivo}): "
            f"HTTP {resp.status_code} — {resp.text[:300]}"
        )
    data = resp.json().get("data", {})
    asset_id = data.get("asset_id")
    if not asset_id:
        raise RuntimeError(f"HeyGen não retornou asset_id: {resp.text[:300]}")
    return asset_id


def gerar_video_heygen_scenes(
    cenas: list[dict],
    disciplina: str,
    heygen_token: str,
    avatar_id: str | None = None,
    voice_id: str | None = None,
) -> str:
    """
    Cria vídeo multi-cenas no HeyGen (v2 Studio API).
    Cada cena = slide de fundo + avatar à direita + fala.

    cenas: [{"fala": "...", "asset_id": "..."}, ...]
    """
    avatar_id = avatar_id or os.getenv("HEYGEN_AVATAR_ID")
    voice_id = voice_id or os.getenv("HEYGEN_VOICE_ID")

    if not avatar_id:
        raise ValueError("HEYGEN_AVATAR_ID não configurado.")
    if not voice_id:
        raise ValueError("HEYGEN_VOICE_ID não configurado.")

    video_inputs = []
    for cena in cenas:
        scene = {
            "character": {
                "type": "talking_photo",
                "talking_photo_id": avatar_id,
                "scale": 0.45,
                "offset": {"x": 0.5, "y": 0.0},
                "talking_photo_style": "square",
                "talking_style": "expressive",
            },
            "voice": {
                "type": "text",
                "voice_id": voice_id,
                "input_text": cena["fala"],
            },
        }

        if cena.get("asset_id"):
            scene["background"] = {
                "type": "image",
                "image_asset_id": cena["asset_id"],
            }
        else:
            scene["background"] = {
                "type": "color",
                "value": HEYGEN_BG_COLOR,
            }

        video_inputs.append(scene)

    headers = {
        "X-Api-Key": heygen_token,
        "Content-Type": "application/json",
    }

    payload = {
        "video_inputs": video_inputs,
        "title": f"Introdução — {disciplina}",
        "dimension": {"width": 1280, "height": 720},
        "caption": False,
    }

    resp = requests.post(
        f"{HEYGEN_BASE_URL}/v2/video/generate",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if not resp.ok:
        raise RuntimeError(
            f"HeyGen /v2/video/generate falhou: "
            f"HTTP {resp.status_code} — {resp.text[:300]}"
        )

    data = resp.json().get("data", {})
    video_id = data.get("video_id")
    if not video_id:
        raise RuntimeError(f"HeyGen não retornou video_id: {resp.text[:300]}")

    return video_id


# =============================================================================
# UTILITÁRIO OPENAI
# =============================================================================

def _chamar_openai(prompt: str, token: str, max_tokens: int = 4000) -> str:
    client = OpenAI(api_key=token)

    for tentativa in range(3):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            erro = str(e)
            if "401" in erro or "invalid_api_key" in erro.lower():
                raise RuntimeError(f"OpenAI: chave inválida. Verifique OPENAI_API_KEY. Detalhe: {erro}")
            if tentativa < 2:
                espera = 5 * (tentativa + 1)
                print(f"⚠️ OpenAI tentativa {tentativa + 1}/3 falhou. Aguardando {espera}s...")
                time.sleep(espera)
            else:
                raise RuntimeError(f"OpenAI falhou após 3 tentativas: {erro}")
