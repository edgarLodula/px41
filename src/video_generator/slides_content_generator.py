"""
Gera conteúdo estruturado (título + tópicos) para slides a partir do roteiro
e do markdown da disciplina, usando uma única chamada OpenAI por vídeo.
"""
import json
import os

from openai import OpenAI


def _fallback_item(cena):
    """Conteúdo determinístico quando OpenAI falha ou retorna estrutura inválida."""
    texto  = (cena.get("texto")  or "").strip().strip("()")
    fala   = (cena.get("fala")   or "").strip()
    visual = (cena.get("visual") or "").strip().strip("()")

    titulo = texto or " ".join(fala.split()[:6]) or "Slide"

    topicos = []
    if visual:
        partes = [p.strip() for p in visual.replace(";", ".").split(".") if p.strip()]
        topicos = partes[:5]
    if not topicos and fala:
        palavras = fala.split()
        topicos = [" ".join(palavras[i:i+10]) for i in range(0, min(len(palavras), 40), 10)]
        topicos = topicos[:5]
    if not topicos:
        topicos = ["Conteúdo da disciplina"]

    while len(topicos) < 3:
        topicos.append(topicos[-1])

    return {"titulo": titulo[:60], "topicos": topicos[:5], "destaque": None}


def _validar_e_corrigir(items, cenas):
    """Garante que items tem o mesmo tamanho de cenas e estrutura mínima válida."""
    while len(items) < len(cenas):
        items.append(_fallback_item(cenas[len(items)]))
    items = items[:len(cenas)]

    for i, item in enumerate(items):
        if not isinstance(item.get("titulo"), str) or not item["titulo"].strip():
            item["titulo"] = _fallback_item(cenas[i])["titulo"]
        topicos = item.get("topicos")
        if not isinstance(topicos, list) or len(topicos) < 1:
            item["topicos"] = _fallback_item(cenas[i])["topicos"]
        while len(item["topicos"]) < 3:
            item["topicos"].append(item["topicos"][-1])
        item["topicos"] = item["topicos"][:5]
        if "destaque" not in item:
            item["destaque"] = None

    return items


def _chamar_openai(client, prompt_sistema, prompt_usuario, modelo):
    resp = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user",   "content": prompt_usuario},
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()


_PROMPT_SISTEMA = (
    "Você é especialista em design instrucional de slides acadêmicos para cursos técnicos de saúde. "
    "Gere conteúdo informativo e substantivo para cada slide, com base no material fornecido.\n"
    "Regras obrigatórias:\n"
    "- Tópicos curtos e objetivos (frases ≤ 12 palavras, ≤ 2 linhas cada);\n"
    "- NÃO repita a fala do avatar no slide — o slide complementa, não duplica;\n"
    "- Conteúdo deve trazer informação substantiva do tema (conceitos, definições, exemplos "
    "práticos, números relevantes) extraída do markdown fornecido;\n"
    "- Evite palavras-chave isoladas sem contexto;\n"
    "- Sem citações diretas, sem expressões 'segundo fulano', 'de acordo com';\n"
    "- Pontuação: tópicos com frase usam ';' entre eles e '.' no último; tópicos que são "
    "apenas seções/palavras-chave, sem pontuação;\n"
    "- Idioma: português brasileiro;\n"
    "- 3 a 5 tópicos por slide (mínimo 3, máximo 5);\n"
    "- Título: ≤ 6 palavras, informativo, em português;\n"
    "- destaque: 1 palavra-chave importante da cena, ou null;\n"
    "- Retorne APENAS JSON válido: array com N objetos na mesma ordem das cenas, "
    "sem markdown fences, sem texto antes ou depois.\n"
    "Formato de cada objeto: "
    "{\"titulo\": \"...\", \"topicos\": [\"...\", \"...\", \"...\"], \"destaque\": \"...\" ou null}"
)


def gerar_conteudo_slides(
    markdown: str,
    cenas: list,
    disciplina: str,
    openai_token: str,
) -> list:
    """
    Para cada cena do roteiro, gera conteúdo informativo do slide
    a partir do conteúdo do markdown da disciplina.

    Retorna list[dict] do mesmo tamanho de `cenas`, cada item:
      {
        "titulo":   str,        # título do slide (curto, <= 6 palavras)
        "topicos":  list[str],  # 3 a 5 tópicos curtos (<= 12 palavras cada)
        "destaque": str|None    # 1 palavra-chave para destacar (opcional)
      }
    """
    modelo = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=openai_token)

    cenas_resumo = [
        {
            "indice":        i,
            "fala":          (cena.get("fala")   or "")[:300],
            "visual":        (cena.get("visual") or "")[:200],
            "texto_na_tela": (cena.get("texto")  or "")[:150],
        }
        for i, cena in enumerate(cenas)
    ]

    prompt_usuario = (
        f"Disciplina: {disciplina}\n\n"
        f"Material da disciplina (base de conhecimento):\n{markdown[:8000]}\n\n"
        f"Cenas do roteiro ({len(cenas)} no total):\n"
        f"{json.dumps(cenas_resumo, ensure_ascii=False)}\n\n"
        f"Gere exatamente {len(cenas)} objetos JSON no array, na mesma ordem das cenas."
    )

    # Tentativa 1
    try:
        resposta = _chamar_openai(client, _PROMPT_SISTEMA, prompt_usuario, modelo)
        items = json.loads(resposta)
        if isinstance(items, list):
            return _validar_e_corrigir(items, cenas)
    except Exception as e:
        print(f"   [slides_content] Tentativa 1 falhou: {e}. Retentando...")

    # Tentativa 2 — prompt mais firme, extrai JSON mesmo com texto em volta
    prompt_firme = (
        _PROMPT_SISTEMA
        + "\nATENÇÃO: Você DEVE retornar APENAS o array JSON. "
        "Comece com '[' e termine com ']'. Nenhum texto adicional."
    )
    try:
        resposta = _chamar_openai(client, prompt_firme, prompt_usuario, modelo)
        inicio = resposta.find("[")
        fim = resposta.rfind("]") + 1
        if inicio >= 0 and fim > inicio:
            resposta = resposta[inicio:fim]
        items = json.loads(resposta)
        if isinstance(items, list):
            return _validar_e_corrigir(items, cenas)
    except Exception as e:
        print(f"   [slides_content] Tentativa 2 falhou: {e}. Usando fallback determinístico.")

    return [_fallback_item(cena) for cena in cenas]
