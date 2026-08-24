"""
Detecção automática da área de formação técnica a partir do conteúdo de um arquivo.

Estratégias (em ordem de prioridade):
  1. override manual
  2. título / cabeçalho do documento ("Técnico em X")
  3. heurística por densidade de termos do perfil
  4. LLM como fallback final (requer client OpenAI)

Importa AREA_PROFILES, _ALIASES e get_profile de area_profiles.
NÃO define profiles — isso está em area_profiles.py.
"""
import re
import logging
from pathlib import Path

from src.content_generation.area_profiles import AREA_PROFILES, _ALIASES, get_profile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LEITURA DE AMOSTRA (docx / pdf / txt)
# ---------------------------------------------------------------------------

def _ler_amostra(caminho: str, max_chars: int = 8_000) -> str:
    p = Path(caminho)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    ext = p.suffix.lower()

    if ext == ".docx":
        import zipfile
        from xml.etree import ElementTree as ET
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        root = ET.fromstring(xml)
        partes: list[str] = []
        for para in root.iter(f"{ns}p"):
            t = "".join(n.text or "" for n in para.iter(f"{ns}t"))
            if t.strip():
                partes.append(t)
            if sum(len(x) for x in partes) >= max_chars:
                break
        return "\n".join(partes)[:max_chars]

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            r = PdfReader(str(p))
            texto = ""
            for pag in r.pages[:5]:
                texto += pag.extract_text() or ""
                if len(texto) >= max_chars:
                    break
            return texto[:max_chars]
        except Exception as exc:
            logger.warning("pypdf falhou para '%s': %s — tentando pdfplumber", caminho, exc)
            import pdfplumber
            texto = ""
            with pdfplumber.open(str(p)) as pdf:
                for pag in pdf.pages[:5]:
                    texto += pag.extract_text() or ""
                    if len(texto) >= max_chars:
                        break
            return texto[:max_chars]

    return p.read_text(encoding="utf-8", errors="ignore")[:max_chars]


# ---------------------------------------------------------------------------
# CAMADA 1: TÍTULO ("TÉCNICO EM X")
# ---------------------------------------------------------------------------

def _detectar_por_titulo(texto: str) -> str | None:
    cabecalho = "\n".join(texto.splitlines()[:15]).lower()

    m = re.search(
        r"(?:t[ée]cnico\s+em|curso\s+t[ée]cnico\s+(?:em|de)|t[ée]cnico\s+de)\s+"
        r"([a-zà-ú0-9\s/&-]{3,60}?)(?:\n|$|[—–:|])",
        cabecalho,
        re.IGNORECASE,
    )

    candidatos: list[str] = []
    if m:
        candidatos.append(m.group(1).strip().lower())
    candidatos.append(cabecalho)

    for c in candidatos:
        for alias in sorted(_ALIASES, key=len, reverse=True):
            if alias in c:
                return _ALIASES[alias]
    return None


# ---------------------------------------------------------------------------
# CAMADA 2: HEURÍSTICA POR DENSIDADE DE TERMOS
# ---------------------------------------------------------------------------

def _detectar_por_conteudo_heuristico(texto: str) -> str | None:
    texto_low = texto.lower()
    scores: dict[str, int] = {}
    for key, profile in AREA_PROFILES.items():
        s = 0
        for grupo in ("ambientes_de_trabalho", "equipamentos_tipicos"):
            for termo in profile.get(grupo, []) or []:
                kw = str(termo).split()[0].lower().strip(".,()/")
                if len(kw) >= 5 and kw in texto_low:
                    s += 1
        scores[key] = s

    if not scores:
        return None
    ordenado = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = ordenado[0]
    segundo = ordenado[1] if len(ordenado) > 1 else ("", 0)
    if top[1] >= 4 and top[1] >= 2 * max(segundo[1], 1):
        return top[0]
    return None


# ---------------------------------------------------------------------------
# CAMADA 3: LLM (fallback final)
# ---------------------------------------------------------------------------

def _detectar_por_llm(client, texto: str) -> str | None:
    descricoes = "\n".join(
        f"- {k}: {AREA_PROFILES[k]['nome_curso']}"
        for k in AREA_PROFILES
    )
    prompt = (
        "Identifique a área desta apostila técnica. "
        "Responda APENAS com uma destas chaves, em minúsculo, sem aspas, sem markdown, sem explicação:\n\n"
        f"{descricoes}\n\n"
        f"TRECHO INICIAL DA APOSTILA:\n\"\"\"\n{texto[:5_000]}\n\"\"\"\n\nChave:"
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=20,
    )
    chave = resp.choices[0].message.content.strip().lower().split()[0].strip(".,'\"`")
    chave_resolvida = _ALIASES.get(chave, chave)
    return chave_resolvida if chave_resolvida in AREA_PROFILES else None


# ---------------------------------------------------------------------------
# API PÚBLICA
# ---------------------------------------------------------------------------

def detectar_area_do_input(
    caminho_input: str,
    client=None,
    override: str | None = None,
) -> dict:
    """
    Detecta automaticamente o profile a partir do conteúdo do arquivo de entrada.

    NÃO consulta variáveis de ambiente. NÃO depende do nome do arquivo.

    Retorna:
        {
            "area_key":  "tecnico_eletrotecnica",
            "profile":   { ...dict completo... },
            "estrategia": "titulo" | "heuristica" | "llm" | "override"
        }

    Lança ValueError se não conseguir detectar.
    """
    if override:
        return {
            "area_key": _ALIASES.get(override.strip().lower(), override.strip().lower()),
            "profile": get_profile(override),
            "estrategia": "override",
        }

    texto = _ler_amostra(caminho_input)
    if not texto.strip():
        raise ValueError(f"Arquivo '{caminho_input}' está vazio ou ilegível.")

    for estrategia, detector in (
        ("titulo",     lambda: _detectar_por_titulo(texto)),
        ("heuristica", lambda: _detectar_por_conteudo_heuristico(texto)),
        ("llm",        lambda: _detectar_por_llm(client, texto) if client else None),
    ):
        key = detector()
        if key:
            logger.debug("Área detectada via '%s': %s", estrategia, key)
            return {
                "area_key": key,
                "profile": get_profile(key),
                "estrategia": estrategia,
            }

    raise ValueError(
        f"Não consegui detectar a área do arquivo '{caminho_input}'. "
        f"Use o parâmetro override=<chave>. Chaves disponíveis: "
        f"{sorted(AREA_PROFILES.keys())}"
    )
