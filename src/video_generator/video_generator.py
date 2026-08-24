import os
import re
import time

from openai import OpenAI

from src.content_generation.area_profiles import get_profile


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ============================================================
# PIPELINE DE VÍDEO (roteiro Bloco/[AVATAR] → slides → HeyGen)
# ============================================================

def _parsear_roteiro_blocos(roteiro: str) -> list:
    """
    Converte roteiro no formato 'Bloco N: título' + marcadores [AVATAR]/[VISUAL/B-ROLL]/
    [TEXTO NA TELA] em lista de cenas {fala, visual, texto} compatível com gerar_slides.
    """
    cenas = []
    fala_p, visual_p, texto_p = [], [], []

    def _salvar_cena():
        if fala_p or visual_p or texto_p:
            cenas.append({
                "fala":   " ".join(fala_p).strip(),
                "visual": " ".join(visual_p).strip(),
                "texto":  " ".join(texto_p).strip(),
            })
        fala_p.clear(); visual_p.clear(); texto_p.clear()

    linhas = roteiro.splitlines()
    i = 0
    while i < len(linhas):
        ls = linhas[i].strip()

        if re.match(r'^Bloco\s+\d+[:\s]', ls):
            _salvar_cena()

        elif ls.upper().startswith("[AVATAR]"):
            # Fala pode estar na mesma linha ou entre aspas na(s) linha(s) seguinte(s)
            inline = re.sub(r'^\[AVATAR\]\s*(\([^)]*\))?\s*', '', ls, flags=re.IGNORECASE).strip().strip('"')
            if inline:
                fala_p.append(inline)
            else:
                i += 1
                while i < len(linhas):
                    prox = linhas[i].strip()
                    if prox.startswith("["):
                        i -= 1
                        break
                    limpo = prox.strip('"').strip()
                    if limpo and not limpo.startswith("("):
                        fala_p.append(limpo)
                    elif not limpo:
                        break
                    i += 1

        elif re.match(r'^\[VISUAL', ls, re.IGNORECASE) or re.match(r'^\[B-ROLL', ls, re.IGNORECASE):
            desc = re.sub(r'^\[[^\]]+\]\s*', '', ls).strip("() ")
            if desc:
                visual_p.append(desc)

        elif ls.upper().startswith("[TEXTO NA TELA]"):
            txt = ls[len("[TEXTO NA TELA]"):].strip().strip("() ")
            if txt:
                texto_p.append(txt)

        i += 1

    _salvar_cena()
    return cenas or [{"fala": roteiro[:500], "visual": "", "texto": ""}]


def gerar_video(roteiro: str, caminho_saida: str, pasta_slides: str, disciplina: str):
    """
    Orquestra a pipeline completa para um vídeo:
      roteiro (formato Bloco/[AVATAR]) → slides PNG → avatar HeyGen (fundo verde)
      → composição local (avatar na lateral, sobre o slide) → mp4.

    Variáveis de ambiente necessárias:
      HEYGEN_API_KEY, HEYGEN_AVATAR_ID, HEYGEN_VOICE_ID
    """
    import shutil
    from src.video_generator.slides_generator import gerar_slides
    from src.video_generator.compor_avatar_slides import gerar_video_avatar_no_canto

    heygen_token = os.getenv("HEYGEN_API_KEY")
    if not heygen_token:
        raise ValueError("HEYGEN_API_KEY não configurada.")

    # 1. Parsear roteiro → cenas
    cenas = _parsear_roteiro_blocos(roteiro)

    # 2. Gerar slides (fundo fixo da cena; o avatar é composto por cima, na lateral)
    print(f"   Gerando {len(cenas)} slide(s) em: {pasta_slides}")
    caminhos_slides = gerar_slides(cenas, pasta_slides, disciplina)

    cenas_para_video = [
        {"fala": cena.get("fala", "").strip(), "slide_path": slide, "tipo": cena.get("tipo", "conteudo")}
        for cena, slide in zip(cenas, caminhos_slides)
        if cena.get("fala", "").strip()
    ]
    if not cenas_para_video:
        raise ValueError("Nenhuma cena com fala encontrada no roteiro.")

    # 3. Avatar no HeyGen (fundo verde) + composição local na lateral do slide
    pasta_video = os.path.dirname(caminho_saida)
    if pasta_video:
        os.makedirs(pasta_video, exist_ok=True)

    print(f"   🎬 Gerando {len(cenas_para_video)} cena(s) com avatar na lateral...")
    caminho_temp = gerar_video_avatar_no_canto(
        cenas=cenas_para_video,
        disciplina=disciplina,
        heygen_token=heygen_token,
        avatar_id=os.getenv("HEYGEN_AVATAR_ID"),
        voice_id=os.getenv("HEYGEN_VOICE_ID"),
        pasta_temp=pasta_video,
        openai_token=os.getenv("OPENAI_API_KEY"),
        prompt_contexto=f"{disciplina}. " + os.getenv("SLIDES_MD_CONTEXT", "")[:600],
    )

    # 4. Mover para o destino final se necessário
    if os.path.abspath(caminho_temp) != os.path.abspath(caminho_saida):
        shutil.move(caminho_temp, caminho_saida)
    print(f"   ✅ Vídeo salvo: {caminho_saida}")


def gerar_video_com_slides(
    cenas:          list[dict],
    disciplina:     str,
    caminho_saida:  str,
    pasta_slides:   str,
    heygen_token:   str,
    openai_token:   str | None = None,
    avatar_id:      str | None = None,
    voice_id:       str | None = None,
) -> str:
    """
    Gera o vídeo completo (slides + avatar recortado/posicionado no canto +
    legenda) a partir de cenas JÁ ESTRUTURADAS — o formato que
    `gerador_videos_direto.parsear_cenas_do_roteiro()` devolve:
    [{"numero", "nome", "producao", "angulo", "texto_na_tela", "fala"}, ...]

    Usado pelos dois fluxos de geração de vídeo da api.py (upload/approve e
    /gerador-videos/*), que já têm o roteiro parseado nesse formato — evita
    serializar de volta pra texto e reparsear com `_parsear_roteiro_blocos`
    (que espera um formato de roteiro diferente, "Bloco N"/"[AVATAR]").
    """
    import shutil
    from src.video_generator.slides_generator import gerar_slides
    from src.video_generator.compor_avatar_slides import gerar_video_avatar_no_canto

    if not heygen_token:
        raise ValueError("HEYGEN_API_KEY não configurada.")

    cenas_slides = [
        {
            "fala":   (c.get("fala") or "").strip(),
            "visual": (c.get("producao") or c.get("angulo") or "").strip(),
            "texto":  (c.get("texto_na_tela") or "").strip(),
            "tipo":   (c.get("tipo") or "conteudo").lower(),
        }
        for c in cenas
        if (c.get("fala") or "").strip()
    ]
    if not cenas_slides:
        raise ValueError(f"Nenhuma cena com fala encontrada para '{disciplina}'.")

    print(f"   Gerando {len(cenas_slides)} slide(s) em: {pasta_slides}")
    caminhos_slides = gerar_slides(cenas_slides, pasta_slides, disciplina)

    cenas_para_video = [
        {"fala": cena["fala"], "slide_path": slide, "tipo": cena.get("tipo", "conteudo")}
        for cena, slide in zip(cenas_slides, caminhos_slides)
    ]

    pasta_video = os.path.dirname(caminho_saida)
    if pasta_video:
        os.makedirs(pasta_video, exist_ok=True)

    print(f"   🎬 Gerando {len(cenas_para_video)} cena(s) com avatar na lateral...")
    caminho_temp = gerar_video_avatar_no_canto(
        cenas=cenas_para_video,
        disciplina=disciplina,
        heygen_token=heygen_token,
        avatar_id=avatar_id or os.getenv("HEYGEN_AVATAR_ID"),
        voice_id=voice_id or os.getenv("HEYGEN_VOICE_ID"),
        pasta_temp=pasta_video or None,
        openai_token=openai_token or os.getenv("OPENAI_API_KEY"),
        prompt_contexto=f"{disciplina}.",
    )

    if os.path.abspath(caminho_temp) != os.path.abspath(caminho_saida):
        shutil.move(caminho_temp, caminho_saida)
    print(f"   ✅ Vídeo salvo: {caminho_saida}")
    return caminho_saida


def configurar_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY não encontrada no .env.")
    client = OpenAI(api_key=api_key)
    print(f"OpenAI configurado (modelo: {OPENAI_MODEL})")
    return client


def _tratar_erro_openai(erro: str, tentativa: int, max_tentativas: int):
    if "401" in erro or "authentication" in erro.lower() or "invalid_api_key" in erro.lower():
        raise Exception(f"Chave OpenAI inválida. Detalhe: {erro}")
    elif "429" in erro or "503" in erro or "500" in erro:
        espera = (2 ** tentativa) * 15
        print(f"Rate limit. Aguardando {espera}s... ({tentativa + 1}/{max_tentativas})")
        time.sleep(espera)
    else:
        raise Exception(f"Erro inesperado na OpenAI: {erro}")


def _chamar_api(client, prompt: str, max_tokens: int = 16000) -> str:
    for tentativa in range(4):
        try:
            resposta = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            return resposta.choices[0].message.content
        except Exception as e:
            _tratar_erro_openai(str(e), tentativa, 4)
    raise Exception("Falha após 4 tentativas.")


def _validar_saida(texto: str, profile: dict) -> str:
    """Avisa (não falha) se a saída contiver vocabulário proibido."""
    proibidos = profile.get("vocabulario_proibido", [])
    encontrados = [p for p in proibidos if p.lower() in texto.lower()]
    if encontrados:
        print(
            f"   ⚠️  AVISO: saída contém termos proibidos para "
            f"{profile['nome_curso']}: {encontrados}"
        )
    return texto


# ============================================================
# HELPERS DE CONTEXTO E REGRAS
# ============================================================

def _bloco_contexto_area(profile: dict) -> str:
    lei = profile.get("lei_exercicio") or "não aplicável"
    return f"""CURSO: {profile['nome_curso']}
ÁREA DE FORMAÇÃO: {profile['nome_area']}
NOME DO PROFISSIONAL FORMADO: {profile['nome_profissional']}
AMBIENTES DE TRABALHO TÍPICOS: {', '.join(profile['ambientes_de_trabalho'])}
EQUIPAMENTOS / MATERIAIS TÍPICOS: {', '.join(profile['equipamentos_tipicos'])}
NORMAS REGULAMENTADORAS APLICÁVEIS: {', '.join(profile['normas_regulamentadoras']) or 'não aplicáveis'}
NORMAS TÉCNICAS APLICÁVEIS: {', '.join(profile['normas_tecnicas']) or 'não aplicáveis'}
CONSELHO DE CLASSE: {profile.get('conselho_classe') or 'não aplicável'}
LEI DE EXERCÍCIO PROFISSIONAL: {lei}
GRANDEZAS / PARÂMETROS TÍPICOS: {profile['grandezas_tipicas']}
EPIs / PROTEÇÕES TÍPICAS: {profile['epis_tipicos'] or 'não aplicáveis'}
PROCEDIMENTOS DE SEGURANÇA CHAVE: {profile['procedimentos_seguranca_chave']}
TECNOLOGIAS EMERGENTES: {profile['tecnologias_emergentes']}
SOFTWARES / SISTEMAS TÍPICOS: {profile['softwares_tipicos']}"""


def _bloco_regras(profile: dict) -> str:
    lei = profile.get("lei_exercicio") or "não aplicável"
    ambientes = ", ".join(profile["ambientes_de_trabalho"][:4])
    nome_curso = profile["nome_curso"]

    proibido_lista = ""
    if profile.get("vocabulario_proibido"):
        itens = "\n".join(f"{i+1}. {t}" for i, t in enumerate(profile["vocabulario_proibido"]))
        proibido_lista = (
            f"VOCABULÁRIO PROIBIDO — NÃO use em hipótese alguma, em nenhuma "
            f"seção, nem como exemplo, nem entre parênteses:\n{itens}"
        )

    refs_lista = ""
    if profile.get("referencias_oficiais_obrigatorias"):
        itens = "\n".join(f"{i+1}. {r}" for i, r in enumerate(profile["referencias_oficiais_obrigatorias"]))
        refs_lista = f"REFERÊNCIAS OFICIAIS QUE DEVEM SER CITADAS quando o tópico permitir:\n{itens}"

    proibido_inline = ", ".join(profile.get("vocabulario_proibido", []))

    return f"""======================================================
RESTRIÇÕES INVIOLÁVEIS DESTE DOCUMENTO
======================================================

ESTE MATERIAL É EXCLUSIVO DO CURSO: **{nome_curso}**.

Sempre que precisar mencionar o nome do curso, use exatamente "{nome_curso}".
NUNCA cite outros cursos técnicos (Enfermagem, Administração, Eletromecânica, etc.)
exceto o curso indicado acima.

Se você violar qualquer item desta lista, o documento é REJEITADO automaticamente.

{proibido_lista}

{refs_lista}

A área desta apostila é {profile['nome_area']}.
O profissional formado é {profile['nome_profissional']}.
Os ambientes de trabalho típicos são: {ambientes}.
O conselho de classe é {profile.get('conselho_classe') or 'não aplicável'}.
A lei de exercício profissional é {lei}.

NUNCA mencione nenhum dos termos da lista de vocabulário proibido acima: {proibido_inline}.

======================================================"""


# ============================================================
# GERADORES DE SEÇÕES GLOBAIS (recebem profile já resolvido)
# ============================================================

def _gerar_introducao(client, disciplina, ementa, contexto, profile):
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    ambientes_lista = "\n".join(f"- {a}" for a in profile["ambientes_de_trabalho"])
    normas_reg = ", ".join(profile["normas_regulamentadoras"]) or "não aplicáveis"
    normas_tec = ", ".join(profile["normas_tecnicas"]) or "não aplicáveis"
    nome_curso = profile["nome_curso"]

    prompt = f"""Você é uma IA especialista sênior em geração de apostilas técnicas profissionalizantes para o curso {nome_curso}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a INTRODUÇÃO COMPLETA E EXPANDIDA da disciplina {disciplina} para uma apostila técnica profissional do curso {nome_curso}.

REGRAS OBRIGATÓRIAS:
- O conteúdo deve ter entre 2.500 e 3.500 palavras (5 a 7 páginas A4).
- Use Markdown estruturado: títulos (##, ###), tabelas quando úteis, negrito para conceitos-chave.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Nunca compacte seções. Desenvolva cada bloco com profundidade real.
- Sempre que se referir ao curso, use o nome EXATO: "{nome_curso}".
- Use segmentação visual: subtítulos claros; evite blocos corridos de mais de 4 parágrafos.
- Onde pertinente, insira marcadores **[FIGURA: descrição detalhada]**.

Use exatamente esta estrutura:

## Apresentação da Disciplina
Contextualize amplamente a disciplina {disciplina} dentro do curso {nome_curso}. Explique o papel central desta disciplina na construção do perfil do {profile['nome_profissional']}. Mínimo de 400 palavras.

## Origem e Evolução Histórica
Trace a história da {disciplina} desde suas origens até o estado atual. Cite marcos, pesquisadores, normas e eventos. Explique como as práticas na área de {profile['nome_area']} evoluíram. Mínimo de 600 palavras.

## Relevância para a Prática Profissional
Explique por que esta disciplina é fundamental para o {profile['nome_profissional']}. Mostre o impacto direto na atuação em ambientes como: {', '.join(profile['ambientes_de_trabalho'][:4])}. Mínimo de 500 palavras.

## Integração Curricular e Interdisciplinaridade
Mostre como {disciplina} se conecta com as demais disciplinas do curso {nome_curso}. Mínimo de 400 palavras.

## O Curso Técnico e o Mercado de Trabalho
Situe {disciplina} no contexto da área de {profile['nome_area']}, abordando os principais ambientes de atuação:
{ambientes_lista}

Explique como normas regulamentadoras ({normas_reg}), normas técnicas ({normas_tec}), exigências do {profile.get('conselho_classe') or 'mercado'} e as demandas do mercado influenciam a prática desta disciplina. Mínimo de 400 palavras.

## Guia de Estudo e Uso desta Apostila
Descreva o percurso de aprendizagem, competências, desafios e orientações práticas. Mínimo de 300 palavras.
"""
    return _validar_saida(_chamar_api(client, prompt, max_tokens=16000), profile)


def _gerar_objetivos(client, disciplina, ementa, contexto, profile):
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    nome_curso = profile["nome_curso"]

    prompt = f"""Você é uma IA especialista sênior em engenharia pedagógica e currículo para o curso {nome_curso}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere os OBJETIVOS DE APRENDIZAGEM COMPLETOS da disciplina {disciplina} para apostila do curso {nome_curso}.

REGRAS OBRIGATÓRIAS:
- 2.000 a 3.000 palavras (4 a 6 páginas A4).
- Markdown estruturado, linguagem técnica formal em pt-BR. Sem emojis.
- Sempre que se referir ao curso, use "{nome_curso}".

Estrutura:

## Objetivos Gerais da Disciplina
5 objetivos gerais, cada um com parágrafo completo. Mínimo de 500 palavras.

## Competências Técnicas a Desenvolver
8 competências práticas específicas para o {profile['nome_profissional']} nos ambientes: {', '.join(profile['ambientes_de_trabalho'][:4])}. Mínimo de 600 palavras.

## Competências Cognitivas e de Raciocínio Técnico
5 competências cognitivas no contexto de {profile['nome_area']}. Mínimo de 400 palavras.

## Competências Atitudinais e Éticas
4 competências atitudinais. Mínimo de 300 palavras.

## Perfil do Aluno ao Concluir a Disciplina
Tabela: Competência | Nível Esperado | Aplicação Profissional. Mínimo de 300 palavras.
"""
    return _validar_saida(_chamar_api(client, prompt, max_tokens=16000), profile)


def _gerar_exemplos(client, disciplina, ementa, contexto, profile):
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    ambientes = profile["ambientes_de_trabalho"]
    equip = ", ".join(profile["equipamentos_tipicos"][:8])
    casos = ambientes[:5] if len(ambientes) >= 5 else ambientes + ["ambiente de trabalho profissional"] * (5 - len(ambientes))
    nome_curso = profile["nome_curso"]

    prompt = f"""Você é uma IA especialista sênior em estudos de caso profissionais do curso {nome_curso}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere 5 ESTUDOS DE CASO PRÁTICOS COMENTADOS da disciplina {disciplina} para o curso {nome_curso}.

REGRAS:
- 4.000 a 5.500 palavras (8 a 11 páginas A4).
- Markdown, linguagem técnica formal pt-BR. Sem emojis.
- Cada caso com no mínimo 700 palavras.
- Sempre que se referir ao curso, use "{nome_curso}".

Casos cobrindo contextos distintos da área de {profile['nome_area']}:
- Caso 1: {casos[0]}
- Caso 2: {casos[1]}
- Caso 3: {casos[2]}
- Caso 4: {casos[3]}
- Caso 5: {casos[4]}

Materiais/equipamentos típicos: {equip}.

Estrutura por caso:

### Caso [N] — [Título]

**Contexto e Descrição do Cenário**
**Análise e Raciocínio Técnico** (com {profile['grandezas_tipicas']}, normas {', '.join(profile['normas_regulamentadoras']) or 'aplicáveis ao setor'})
**Conduta e Execução Técnica** (EPIs: {profile['epis_tipicos'] or 'aplicáveis'}; procedimentos: {profile['procedimentos_seguranca_chave']})
**Desfecho e Resultado**
**Lição Profissional e Pontos Críticos**
"""
    return _validar_saida(_chamar_api(client, prompt, max_tokens=16000), profile)


def _gerar_resumo(client, disciplina, ementa, contexto, profile):
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    ambientes_resumo = ", ".join(profile["ambientes_de_trabalho"][:5])
    nome_curso = profile["nome_curso"]

    prompt = f"""Você é uma IA especialista sênior em material didático técnico do curso {nome_curso}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere o RESUMO TÉCNICO COMPLETO da disciplina {disciplina} para o curso {nome_curso}.

REGRAS:
- 2.500 a 3.500 palavras (5 a 7 páginas A4).
- Markdown estruturado, pt-BR formal. Sem emojis.
- Sempre que se referir ao curso, use "{nome_curso}".

Estrutura:

## Síntese dos Fundamentos Teóricos (mín. 600 palavras)
## Síntese das Competências Práticas (mín. 600 palavras, com checklist)
## Pontos Críticos para a Prática Profissional (7 pontos, mín. 600 palavras)
## Conexões com o Exercício da Profissão (mín. 400 palavras, ambientes: {ambientes_resumo})
## Glossário Técnico da Disciplina (20 termos em tabela, mín. 500 palavras)
"""
    return _validar_saida(_chamar_api(client, prompt, max_tokens=16000), profile)


def _gerar_questoes(client, disciplina, ementa, contexto, profile):
    """Retorna (bloco_aluno, bloco_professor)."""
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    grandezas = profile["grandezas_tipicas"]
    nome_prof = profile["nome_profissional"]
    nome_curso = profile["nome_curso"]

    prompt = f"""Você é uma IA especialista sênior em avaliação pedagógica do curso {nome_curso}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a AVALIAÇÃO GERAL COMPLETA da disciplina {disciplina} para o curso {nome_curso}.

INSTRUÇÃO CRÍTICA: separe a saída com a linha exata abaixo:
===CADERNO_PROFESSOR===

Antes do separador = CADERNO DO ALUNO (só enunciados).
Depois do separador = CADERNO DO PROFESSOR (gabaritos e critérios).

REGRAS:
- Total 3.500 a 5.000 palavras (7 a 10 páginas A4).
- Markdown, pt-BR formal. Sem emojis.
- Use parâmetros numéricos ({grandezas}) onde fizer sentido.
- Sempre que se referir ao curso, use "{nome_curso}".

CADERNO DO ALUNO:

## Parte I — Questões Objetivas (10 questões, A/B/C/D)
## Parte II — Questões Dissertativas (6 questões: 2 conceituais, 2 analíticas, 2 críticas)
## Parte III — Questões Baseadas em Casos Práticos (4 questões com cenários realistas do {nome_prof})

===CADERNO_PROFESSOR===

## Gabarito Comentado — Parte I (≥30 palavras por questão)
## Critérios de Avaliação — Parte II (≥200 palavras por questão)
## Gabarito e Comentários — Parte III (≥300 palavras por questão)
## Competências Avaliadas nesta Prova
"""
    resultado = _chamar_api(client, prompt, max_tokens=16000)
    partes = resultado.split("===CADERNO_PROFESSOR===", 1)
    bloco_aluno = _validar_saida(partes[0].strip(), profile)
    bloco_professor = _validar_saida(partes[1].strip(), profile) if len(partes) > 1 else ""
    return bloco_aluno, bloco_professor


# ============================================================
# FUNÇÕES PÚBLICAS
# ============================================================

def gerar_topico(client, disciplina, topico, contexto, area):
    """Gera o conteúdo completo de um tópico. `area` é obrigatório."""
    profile = get_profile(area)
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    nome_prof = profile["nome_profissional"]
    nome_curso = profile["nome_curso"]
    normas_reg = ", ".join(profile["normas_regulamentadoras"]) or "não aplicáveis"
    normas_tec = ", ".join(profile["normas_tecnicas"]) or "não aplicáveis"
    ambientes_lista = "\n".join(f"- {a}" for a in profile["ambientes_de_trabalho"])
    grandezas = profile["grandezas_tipicas"]

    prompt = f"""Você é uma IA especialista sênior em apostilas técnicas do curso {nome_curso}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO COMPLEMENTAR: {contexto}

Gere o conteúdo COMPLETO do tópico "{topico}" da disciplina {disciplina} para apostila do curso {nome_curso}.

REGRAS EDITORIAIS OBRIGATÓRIAS:
- 5.000 a 7.500 palavras (10 a 15 páginas A4).
- Markdown (##, ###, ####), tabelas, negrito para conceitos-chave.
- **Atenção:** para alertas. **Dica do Técnico:** para boas práticas. **Revisão Rápida:** ao fim das fundamentações.
- Checklists com - [ ] item.
- **[FIGURA: descrição]** onde imagens devem entrar.
- pt-BR formal, sem emojis.
- Sempre que se referir ao curso, use "{nome_curso}".

Estrutura obrigatória (13 seções):

## 1. Abertura do Tópico
Objetivos de Aprendizagem (4-6 competências) + contextualização para o {nome_prof}. Mín. 300 palavras.

## 2. Fundamentação Teórica Aprofundada
Conceitos, evolução histórica, fundamentos, normas ({normas_reg}, {normas_tec}), parâmetros ({grandezas}) com exemplo resolvido. Mín. 900 palavras.

## 3. Conceitos Fundamentais
6+ conceitos centrais, cada um com: definição técnica precisa, explicação didática, exemplo prático em {profile['nome_area']}, erro comum, consequência e prevenção. Mín. 800 palavras.

## 4. Aprofundamento Técnico
Situações especiais, exceções, critérios de decisão do {nome_prof}, sinais de alerta, riscos, conexões com outros tópicos. Aborde tecnologias: {profile['tecnologias_emergentes']}; softwares: {profile['softwares_tipicos']}; segurança: {profile['procedimentos_seguranca_chave']}. Mín. 700 palavras.

## 5. Aplicação Prática Profissional
Como o {nome_prof} usa este conteúdo em pelo menos 3 ambientes distintos:
{ambientes_lista}
Mín. 800 palavras.

## 6. Procedimentos, Protocolos e Boas Práticas
Checklist passo a passo (- [ ] item) com EPIs ({profile['epis_tipicos'] or 'não aplicáveis'}), normas ({normas_reg}), procedimentos ({profile['procedimentos_seguranca_chave']}). Mín. 700 palavras.

## 7. Segurança, Ética e Responsabilidade Profissional
Riscos, postura ética, responsabilidade técnica/legal ({profile.get('conselho_classe') or 'aplicável ao setor'}), limites de atuação. Mín. 500 palavras.

## 8. Estudos de Caso Comentados
2 casos completos com Cenário, Situação-problema, Dados, Decisão esperada, Conduta correta, Erro comum, Consequência, Raciocínio, Lição. Mín. 600 palavras.

## 9. Erros Comuns e Como Evitar
6 erros desenvolvidos. Mín. 500 palavras.

## 10. Integração com Outros Tópicos e Disciplinas
Conexões dentro de {disciplina} e com outras disciplinas do curso {nome_curso}. Mín. 300 palavras.

## 11. Resumo Técnico do Tópico
Quadro de Revisão Rápida. 200-300 palavras.

## 12. Glossário do Tópico
10 termos com definição, explicação didática, exemplo em {profile['nome_area']}, cuidado/erro comum. Mín. 400 palavras.

## 13. Carreira e Empregabilidade
Segmentos ({', '.join(profile['ambientes_de_trabalho'][:4])}), cargos, certificações ({normas_reg}, {profile.get('conselho_classe') or ''}), dicas, tendências: {profile['tecnologias_emergentes']}. Mín. 250 palavras.
"""
    return _validar_saida(_chamar_api(client, prompt, max_tokens=16000), profile)


def gerar_questoes_topico(client, disciplina, topico, contexto, area):
    """Retorna (bloco_aluno, bloco_professor). `area` é obrigatório."""
    profile = get_profile(area)
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    grandezas = profile["grandezas_tipicas"]
    nome_prof = profile["nome_profissional"]
    nome_curso = profile["nome_curso"]

    prompt = f"""Você é uma IA especialista sênior em avaliação pedagógica do curso {nome_curso}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO COMPLEMENTAR: {contexto}

Gere PERGUNTAS E EXERCÍCIOS do tópico "{topico}" da disciplina {disciplina} para o curso {nome_curso}.

INSTRUÇÃO CRÍTICA: separe com a linha exata:
===CADERNO_PROFESSOR===

Antes = CADERNO DO ALUNO (enunciados). Depois = CADERNO DO PROFESSOR (gabarito).

REGRAS:
- Total 500 a 700 palavras (1 página A4).
- Markdown, pt-BR formal, sem emojis.
- Use parâmetros numéricos ({grandezas}) onde fizer sentido.
- Sempre que se referir ao curso, use "{nome_curso}".

CADERNO DO ALUNO:

### Questoes Objetivas
5 questões A/B/C/D.

Q1. [Enunciado]
A) [opcao]  B) [opcao]  C) [opcao]  D) [opcao]

(Q2 a Q5 no mesmo formato)

### Questoes Dissertativas
3 questões dissertativas para situações reais do {nome_prof}.

D1. [Enunciado]
D2. [Enunciado]
D3. [Enunciado]

### Questoes Baseadas em Caso Pratico
2 cenários realistas da área de {profile['nome_area']}.

CP1. [Cenário e enunciado]
CP2. [Cenário e enunciado]

===CADERNO_PROFESSOR===

### Gabarito e Criterios de Avaliacao

**Gabarito objetivas:** Q1-[letra] | Q2-[letra] | Q3-[letra] | Q4-[letra] | Q5-[letra]
**Comentário das respostas objetivas:** explique cada uma.
**Critérios D1, D2, D3, CP1, CP2:** pontos essenciais.
**Competências avaliadas:** [lista]
"""
    resultado = _chamar_api(client, prompt, max_tokens=4000)
    partes = resultado.split("===CADERNO_PROFESSOR===", 1)
    bloco_aluno = _validar_saida(partes[0].strip(), profile)
    bloco_professor = _validar_saida(partes[1].strip(), profile) if len(partes) > 1 else ""
    return bloco_aluno, bloco_professor


def gerar_documento(client, disciplina, ementa, conteudo, contexto, area):
    """Roteador. `area` é obrigatório."""
    profile = get_profile(area)
    instrucao = conteudo.lower()

    if "introdução" in instrucao or "introducao" in instrucao:
        return _gerar_introducao(client, disciplina, ementa, contexto, profile)
    elif "objetivo" in instrucao:
        return _gerar_objetivos(client, disciplina, ementa, contexto, profile)
    elif "exemplo" in instrucao or "caso" in instrucao or "prático" in instrucao:
        return _gerar_exemplos(client, disciplina, ementa, contexto, profile)
    elif "resumo" in instrucao or "síntese" in instrucao:
        return _gerar_resumo(client, disciplina, ementa, contexto, profile)
    elif "questão" in instrucao or "quest" in instrucao or "dissertat" in instrucao or "avaliação" in instrucao:
        return _gerar_questoes(client, disciplina, ementa, contexto, profile)
    else:
        ctx = _bloco_contexto_area(profile)
        regras = _bloco_regras(profile)
        nome_curso = profile["nome_curso"]
        prompt = f"""Você é uma IA especialista sênior em material didático do curso {nome_curso}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
INSTRUÇÃO: {conteudo}
CONTEXTO: {contexto}

Gere 2.000 a 3.000 palavras. Markdown, pt-BR formal, sem emojis.
Orientado ao curso {nome_curso}, com exemplos em {', '.join(profile['ambientes_de_trabalho'][:3])} e situações reais do {profile['nome_profissional']}.
"""
        return _validar_saida(_chamar_api(client, prompt, max_tokens=16000), profile)