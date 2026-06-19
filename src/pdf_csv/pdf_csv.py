"""
Extração de PDF de conteúdo programático para CSV.

O conteúdo programático de cada célula é normalizado por `normalizar_topicos_celula`
para recompor tópicos quebrados em múltiplas linhas.
"""
import re
import csv
import os
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MARCADORES DE INÍCIO DE ITEM
# ---------------------------------------------------------------------------
_RE_MARCADOR = re.compile(
    r"^(?:"
    r"\s*[-–—•*]\s+"         # hífen, travessão, bullet
    r"|\s*\d+[.)]\s+"        # numeração 1. 1) 2. 2)
    r"|\s*[a-z][.)]\s+"      # letra a) b)
    r")",
    re.IGNORECASE,
)

# Palavras que indicam continuação de linha (minúsculas, preposições, conjunções)
_PALAVRAS_CONTINUACAO = frozenset({
    "a", "à", "ao", "aos", "às", "as", "de", "do", "da", "dos", "das",
    "e", "em", "no", "na", "nos", "nas", "o", "os", "por", "para",
    "com", "sem", "que", "ou", "num", "numa", "se", "sua", "seu",
})


# ---------------------------------------------------------------------------
# CORREÇÃO MANUAL DE CSV
# ---------------------------------------------------------------------------

def aplicar_correcoes(caminho_csv: str, caminho_correcoes: str = None) -> int:
    """
    Aplica correções manuais definidas em um JSON ao CSV gerado.

    O JSON deve ter a estrutura:
        {
            "Nome do Curso": {
                "Nome da Disciplina": {
                    "ementa_completar": "texto a acrescentar",
                    "topicos_adicionais": ["Tópico 4", "Tópico 5"]
                }
            }
        }

    Retorna o número de linhas modificadas.
    """
    if caminho_correcoes is None:
        caminho_correcoes = os.path.join(
            os.path.dirname(caminho_csv), "correcoes_csv.json"
        )

    if not os.path.exists(caminho_correcoes):
        return 0

    with open(caminho_correcoes, "r", encoding="utf-8") as f:
        correcoes = json.load(f)

    with open(caminho_csv, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        linhas = list(reader)

    if not linhas:
        return 0

    corrigidas = 0
    for linha in linhas:
        curso = linha.get("Curso", "")
        disciplina = linha.get("Disciplina", "").replace("\n", " ").strip()

        if curso not in correcoes:
            continue
        if disciplina not in correcoes[curso]:
            continue

        correcao = correcoes[curso][disciplina]

        # Completa ementa truncada
        if "ementa_completar" in correcao:
            ementa_atual = linha.get("Ementa", "").strip()
            complemento = correcao["ementa_completar"]
            if complemento not in ementa_atual:
                linha["Ementa"] = ementa_atual.rstrip() + " " + complemento
                corrigidas += 1

        # Adiciona tópicos faltantes
        if "topicos_adicionais" in correcao:
            topicos_atuais = linha.get("Conteudo_Programatico", "")
            for topico in correcao["topicos_adicionais"]:
                topicos_atuais += f" | {topico}"
            linha["Conteudo_Programatico"] = topicos_atuais
            corrigidas += 1

    with open(caminho_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=linhas[0].keys())
        writer.writeheader()
        writer.writerows(linhas)

    logger.info("Correções aplicadas: %d linha(s)", corrigidas)
    return corrigidas


# ---------------------------------------------------------------------------
# NORMALIZAÇÃO DE TÓPICOS DE CÉLULA
# ---------------------------------------------------------------------------

def normalizar_topicos_celula(texto: str) -> list[str]:
    """
    Recebe o texto bruto de uma célula de conteúdo programático
    e retorna lista de tópicos recompostos.

    Regras:
    - Linhas iniciadas por marcador (-·• 1. a)) começam novo item.
    - Linhas sem marcador que começam com letra minúscula, preposição
      ou conjunção são unidas à linha anterior (continuação).
    - Linhas vazias são ignoradas.
    """
    if not texto or not texto.strip():
        return []

    linhas = texto.splitlines()
    topicos: list[str] = []
    atual: str = ""

    for linha in linhas:
        stripped = linha.strip()
        if not stripped:
            continue

        if _RE_MARCADOR.match(stripped):
            # Nova linha com marcador → fecha item anterior e inicia novo
            if atual:
                topicos.append(atual.strip())
            # Remove o marcador do conteúdo
            atual = _RE_MARCADOR.sub("", stripped).strip()
        else:
            # Linha sem marcador: é continuação?
            primeira_palavra = stripped.split()[0].rstrip(",.;:").lower() if stripped else ""
            primeira_char = stripped[0] if stripped else ""

            eh_continuacao = (
                primeira_char.islower()
                or primeira_palavra in _PALAVRAS_CONTINUACAO
            )

            if atual and eh_continuacao:
                # Continua o item anterior
                atual = atual.rstrip() + " " + stripped
            elif atual:
                # Linha nova sem marcador explícito — une se o atual não termina com pontuação
                if atual[-1] not in ".!?:":
                    atual = atual.rstrip() + " " + stripped
                else:
                    topicos.append(atual.strip())
                    atual = stripped
            else:
                atual = stripped

    if atual:
        topicos.append(atual.strip())

    return [t for t in topicos if t]


# ---------------------------------------------------------------------------
# EXTRAÇÃO DO PDF
# ---------------------------------------------------------------------------

def extrair_pdf_para_csv(caminho_pdf: str, caminho_csv: str) -> None:
    """Extrai tabela de conteúdo programático do PDF e salva como CSV."""
    import pdfplumber  # lazy import — não obrigatório para normalizar_topicos_celula
    os.makedirs(os.path.dirname(caminho_csv) or ".", exist_ok=True)

    registros: list[dict] = []

    with pdfplumber.open(caminho_pdf) as pdf:
        texto_primeira_pagina = pdf.pages[0].extract_text() or ""
        nome_curso = (
            texto_primeira_pagina.split("\n")[0].strip()
            if texto_primeira_pagina
            else os.path.basename(caminho_pdf)
        )

        for pagina in pdf.pages:
            for tabela in (pagina.extract_tables() or []):
                for linha in tabela:
                    if len(linha) < 3:
                        continue
                    if not linha[0] or not linha[2]:
                        continue
                    if linha[0].strip().lower() == "disciplina":
                        continue

                    conteudo_raw = (linha[2] or "").strip()
                    topicos = normalizar_topicos_celula(conteudo_raw)
                    conteudo_normalizado = " | ".join(topicos) if topicos else conteudo_raw

                    registros.append({
                        "Curso": nome_curso,
                        "Disciplina": linha[0].strip(),
                        "Ementa": (linha[1] or "").strip(),
                        "Conteudo_Programatico": conteudo_normalizado,
                    })

    fieldnames = ["Curso", "Disciplina", "Ementa", "Conteudo_Programatico"]
    with open(caminho_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(registros)

    logger.info("CSV salvo em '%s' (%d registros)", caminho_csv, len(registros))
    print(f"✅ CSV salvo em: {caminho_csv} ({len(registros)} registros)")
