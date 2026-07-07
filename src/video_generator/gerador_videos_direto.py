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
import shutil
import subprocess
import tempfile
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
HEYGEN_SPEED = float(os.getenv("HEYGEN_SPEED", "1.0"))              # 0.5–2.0
HEYGEN_EXPRESSIVENESS = os.getenv("HEYGEN_EXPRESSIVENESS", "high")   # "low" | "medium" | "high"
HEYGEN_MOTION_PROMPT  = os.getenv("HEYGEN_MOTION_PROMPT", (
    "warm, confident instructor with natural human body language: "
    "uses both hands expressively and fluidly to emphasize key points, "
    "open-palm gestures while explaining concepts, occasional finger-counting "
    "when listing items, subtle shifts in posture and weight between sentences, "
    "natural head tilts and nods on important words, expressive eyebrows and "
    "genuine smiles, brief thoughtful pauses with eyes slightly raised before "
    "continuing, frequent natural eye contact with the camera, relaxed shoulders, "
    "varied gesture timing and amplitude so the movement never feels repetitive "
    "or robotic — like a real teacher speaking spontaneously"
))
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
    fala:         str,
    disciplina:   str,
    heygen_token: str,
    avatar_id:    str | None = None,
    voice_id:     str | None = None,
    motion_prompt: str | None = None
) -> str:
    """
    Envia uma fala para HeyGen v3 e retorna o video_id.
    Para múltiplas cenas com slides, use gerar_video_v3_multicena.
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
        "type":          "avatar",
        "avatar_id":     avatar_id,
        "voice_id":      voice_id,
        "script":        fala if not LIMITE_PALAVRAS else _truncar_palavras(fala, LIMITE_PALAVRAS),
        "title":         disciplina,
        "aspect_ratio":  HEYGEN_ASPECT_RATIO,
        "voice_settings": {
            "speed": HEYGEN_SPEED,
            "locale":os.getenv("HEYGEN_VOICE_LOCALE","pt-BR")},
        "motion_prompt": motion_prompt or HEYGEN_MOTION_PROMPT,
        "expressiveness": HEYGEN_EXPRESSIVENESS,
        "engine":        {"type": HEYGEN_ENGINE},
        "background":    (
            {"type": "image", "asset_id": HEYGEN_BG_ASSET_ID}
            if HEYGEN_BG_ASSET_ID
            else {"type": "color", "value": HEYGEN_BG_COLOR}
        ),
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

    video_id = resp.json().get("data", {}).get("video_id")
    if not video_id:
        raise RuntimeError(f"HeyGen não retornou video_id: {resp.text[:300]}")
    return video_id


def gerar_video_v3_multicena(
    cenas_com_slides: list[dict],
    disciplina:       str,
    heygen_token:     str,
    avatar_id:        str | None = None,
    voice_id:         str | None = None,
    pasta_temp:       str | None = None,
) -> str:
    """
    Processa múltiplas cenas com slides via HeyGen v3, baixa cada vídeo
    e os concatena com ffmpeg. Retorna o caminho do vídeo final.

    cenas_com_slides: [{"fala": "...", "asset_id": "..."}, ...]
    """
    avatar_id  = avatar_id  or os.getenv("HEYGEN_AVATAR_ID")
    voice_id   = voice_id   or os.getenv("HEYGEN_VOICE_ID")
    pasta_temp = pasta_temp or tempfile.mkdtemp(prefix="heygen_v3_")

    if not avatar_id:
        raise ValueError("HEYGEN_AVATAR_ID não configurado.")
    if not voice_id:
        raise ValueError("HEYGEN_VOICE_ID não configurado.")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg não encontrado no PATH.")

    os.makedirs(pasta_temp, exist_ok=True)
    caminhos_cena: list[str] = []
    total = len(cenas_com_slides)

    for i, cena in enumerate(cenas_com_slides, 1):
        fala     = cena["fala"].strip()
        asset_id = cena.get("asset_id")
        if not fala:
            print(f"   ⚠️ Cena {i}/{total} sem fala — pulando")
            continue

        print(f"   📹 Cena {i}/{total} — {len(fala)} chars de fala")
        bg = (
            {"type": "image", "asset_id": asset_id}
            if asset_id
            else {"type": "color", "value": HEYGEN_BG_COLOR}
        )

        headers = {
            "X-Api-Key":       heygen_token,
            "Content-Type":    "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        }
        payload = {
            "type":           "avatar",
            "avatar_id":      avatar_id,
            "voice_id":       voice_id,
            "script":         fala if not LIMITE_PALAVRAS else _truncar_palavras(fala, LIMITE_PALAVRAS),
            "title":          f"{disciplina} — Cena {i}/{total}",
            "aspect_ratio":   HEYGEN_ASPECT_RATIO,
            "voice_settings": {
            "speed": HEYGEN_SPEED,
            "locale":os.getenv("HEYGEN_VOICE_LOCALE","pt-BR")},
            "motion_prompt": cena.get("motion_prompt") or HEYGEN_MOTION_PROMPT,
            "expressiveness": cena.get("expressiveness") or HEYGEN_EXPRESSIVENESS,
            "engine":         {"type": HEYGEN_ENGINE},
            "background":     bg,
        }

        resp = requests.post(
            f"{HEYGEN_BASE_URL}/v3/videos",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"HeyGen cena {i}: HTTP {resp.status_code} — {resp.text[:300]}")

        video_id = resp.json().get("data", {}).get("video_id")
        if not video_id:
            raise RuntimeError(f"Sem video_id na cena {i}: {resp.text[:300]}")

        print(f"      video_id: {video_id}")
        info = aguardar_video(video_id, heygen_token, max_min=5.0)
        if not info.get("video_url"):
            raise RuntimeError(f"Sem video_url na cena {i}")

        cp = os.path.abspath(os.path.join(pasta_temp, f"cena_{i:03d}.mp4"))
        r = requests.get(info["video_url"], timeout=120)
        r.raise_for_status()
        with open(cp, "wb") as f:
            f.write(r.content)
        print(f"      ✅ {os.path.getsize(cp) // 1024} KB")
        caminhos_cena.append(cp)

    if not caminhos_cena:
        raise RuntimeError("Nenhuma cena gerada.")
    if len(caminhos_cena) == 1:
        return caminhos_cena[0]

    lista = os.path.abspath(os.path.join(pasta_temp, "concat.txt"))
    final = os.path.abspath(os.path.join(
        pasta_temp,
        f"{re.sub(r'[^\w\-]', '_', disciplina)}_final.mp4",
    ))
    with open(lista, "w", encoding="utf-8") as f:
        for c in caminhos_cena:
            f.write(f"file '{c.replace(chr(92), '/')}'\n")

    print(f"   🔗 Concatenando {len(caminhos_cena)} vídeos...")
    r = subprocess.run(
        ["ffmpeg", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", final, "-y"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if r.returncode != 0:
        r = subprocess.run(
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", lista,
             "-c:v", "libx264", "-c:a", "aac", final, "-y"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg falhou: {r.stderr[:300]}")

    print(f"   ✅ Final: {final} ({os.path.getsize(final) / 1024 / 1024:.1f} MB)")
    return final


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


def _enviar_video_generate_com_retry(headers: dict, payload: dict, max_espera_min: int = 10):
    """
    POST /v2/video/generate com retry específico para o erro
    'Avatar ... is still processing' (avatar customizado ainda em criação no HeyGen).
    Outros erros HTTP são propagados imediatamente.
    """
    tentativas = max(1, (max_espera_min * 60) // 20)
    for tentativa in range(tentativas):
        resp = requests.post(
            f"{HEYGEN_BASE_URL}/v2/video/generate",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if resp.ok:
            return resp
        if resp.status_code == 400 and "still processing" in resp.text.lower():
            print(
                f"   [AVISO] Avatar ainda em processamento no HeyGen. "
                f"Aguardando 20s antes de tentar novamente... ({tentativa + 1}/{tentativas})"
            )
            time.sleep(20)
            continue
        raise RuntimeError(
            f"HeyGen /v2/video/generate falhou: "
            f"HTTP {resp.status_code} — {resp.text[:300]}"
        )

    raise RuntimeError(
        f"Avatar ainda em processamento no HeyGen após {max_espera_min} min de espera. "
        "Aguarde a criação do avatar terminar (verifique no painel HeyGen) e tente novamente."
    )


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
        fala = cena["fala"]
        if LIMITE_PALAVRAS:
            fala = _truncar_palavras(fala, LIMITE_PALAVRAS)

        scene = {
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal",
                "motion_prompt": cena.get("motion_prompt") or HEYGEN_MOTION_PROMPT,
                "expressiveness": cena.get("expressiveness") or HEYGEN_EXPRESSIVENESS,
            },
            "voice": {
                "type": "text",
                "voice_id": voice_id,
                "input_text": fala,
                "speed": HEYGEN_SPEED,
                "locale":os.getenv("HEYGEN_VOICE_LOCALE","pt-BR")
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

    resp = _enviar_video_generate_com_retry(headers, payload)

    data = resp.json().get("data", {})
    video_id = data.get("video_id")
    if not video_id:
        raise RuntimeError(f"HeyGen não retornou video_id: {resp.text[:300]}")

    return video_id


# =============================================================================
# ETAPA 4b — CENAS APROVADAS → VÍDEO VIA TEMPLATE (Studio Avatar com gestos)
# =============================================================================

def _detectar_var_texto(template_id: str, heygen_token: str) -> str:
    """
    Consulta o template e retorna o nome da primeira variável de texto encontrada.
    Fallback: env HEYGEN_SCENE_VAR ou 'script'.
    """
    fallback = os.getenv("HEYGEN_SCENE_VAR", "script")
    try:
        resp = requests.get(
            f"{HEYGEN_BASE_URL}/v2/template/{template_id}",
            headers={"X-Api-Key": heygen_token},
            timeout=15,
        )
        if not resp.ok:
            return fallback
        variables = resp.json().get("data", {}).get("variables", {})
        for name, var in variables.items():
            if var.get("type") == "text":
                print(f"   ℹ️  Variável de texto do template detectada: '{name}'")
                return name
    except Exception:
        pass
    return fallback


def gerar_video_template_multicena(
    cenas_com_slides: list[dict],
    disciplina:       str,
    heygen_token:     str,
    template_id:      str,
    pasta_temp:       str | None = None,
) -> str:
    """
    Gera um vídeo por cena usando um template HeyGen (Studio Avatar com gestos).
    O layout/background/avatar vêm da cena — apenas o texto varia por chamada.
    Concatena os vídeos individuais com ffmpeg.

    cenas_com_slides: [{"fala": "..."}, ...]  (asset_id ignorado — template define o visual)
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg não encontrado no PATH.")

    pasta_temp = pasta_temp or tempfile.mkdtemp(prefix="heygen_tmpl_")
    os.makedirs(pasta_temp, exist_ok=True)

    var_nome = _detectar_var_texto(template_id, heygen_token)
    headers  = {"X-Api-Key": heygen_token, "Content-Type": "application/json"}

    caminhos_cena: list[str] = []
    total = len(cenas_com_slides)

    for i, cena in enumerate(cenas_com_slides, 1):
        fala = cena["fala"].strip()
        if not fala:
            print(f"   ⚠️ Cena {i}/{total} sem fala — pulando")
            continue

        print(f"   📹 Cena {i}/{total} — {len(fala)} chars de fala")

        payload = {
            "test":    False,
            "caption": False,
            "title":   f"{disciplina} — Cena {i}/{total}",
            "variables": {
                var_nome: {
                    "name":       var_nome,
                    "type":       "text",
                    "properties": {
                        "content": fala if not LIMITE_PALAVRAS else _truncar_palavras(fala, LIMITE_PALAVRAS),
                    },
                }
            },
        }

        resp = requests.post(
            f"{HEYGEN_BASE_URL}/v2/template/{template_id}/generate",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(
                f"HeyGen template cena {i}: HTTP {resp.status_code} — {resp.text[:300]}"
            )

        video_id = resp.json().get("data", {}).get("video_id")
        if not video_id:
            raise RuntimeError(f"Sem video_id na cena {i}: {resp.text[:300]}")

        print(f"      video_id: {video_id}")
        info = aguardar_video(video_id, heygen_token, max_min=5.0)
        if not info.get("video_url"):
            raise RuntimeError(f"Sem video_url na cena {i}")

        cp = os.path.join(pasta_temp, f"cena_{i:03d}.mp4")
        r = requests.get(info["video_url"], timeout=120)
        r.raise_for_status()
        with open(cp, "wb") as f:
            f.write(r.content)
        print(f"      ✅ {os.path.getsize(cp) // 1024} KB")
        caminhos_cena.append(cp)

    if not caminhos_cena:
        raise RuntimeError("Nenhuma cena gerada.")
    if len(caminhos_cena) == 1:
        return caminhos_cena[0]

    lista = os.path.join(pasta_temp, "concat.txt")
    final = os.path.join(
        pasta_temp,
        f"{re.sub(r'[^\w\-]', '_', disciplina)}_final.mp4",
    )
    with open(lista, "w") as f:
        for c in caminhos_cena:
            f.write(f"file '{c}'\n")

    print(f"   🔗 Concatenando {len(caminhos_cena)} vídeos...")
    r = subprocess.run(
        ["ffmpeg", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", final, "-y"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if r.returncode != 0:
        r = subprocess.run(
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", lista,
             "-c:v", "libx264", "-c:a", "aac", final, "-y"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg falhou: {r.stderr[:300]}")

    print(f"   ✅ Final: {final} ({os.path.getsize(final) / 1024 / 1024:.1f} MB)")
    return final


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
