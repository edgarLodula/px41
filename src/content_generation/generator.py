"""
Gerador de conteúdo de apostilas via OpenAI.

Todas as funções de geração recebem `profile` explicitamente.
Nenhuma função consulta AREA_FORMACAO nem variáveis de ambiente para definir área.
"""
import os
import time
import logging
import re

from openai import OpenAI

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_RETRY_SLEEP_FN = time.sleep  # substituível em testes (injeção de dependência)

_PADROES_PROMPT_VAZADO = [
    re.compile(r"^\s*(Crie|Gere|Elabore|Produza|Escreva)\s+\d+\s+quest[õo]es.*$",
               re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*TAREFAS DE GERAÇÃO.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*T\d+\.\s+(Gere|Crie|Elabore|Produza|Escreva).*$",
               re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*FORMATO DE SAÍDA.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^={5,}$", re.MULTILINE),
]


def _limpar_vazamentos_prompt(texto: str) -> str:
    if not texto:
        return texto
    for padrao in _PADROES_PROMPT_VAZADO:
        texto = padrao.sub("", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DO CLIENT
# ---------------------------------------------------------------------------

def configurar_openai() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY não encontrada. "
            "Defina a variável de ambiente ou adicione ao arquivo .env"
        )
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI configurado (modelo: %s)", OPENAI_MODEL)
    return client


# ---------------------------------------------------------------------------
# TRATAMENTO DE ERROS DA API
# ---------------------------------------------------------------------------

_ERROS_TRANSITORIOS = ("429", "503", "500", "502", "504", "rate_limit")
_ERROS_CONFIGURACAO = ("401", "authentication", "invalid_api_key",
                        "invalid_request_error", "400")


def _tratar_erro_openai(exc: Exception, tentativa: int, max_tentativas: int) -> None:
    """
    Decide entre re-raise imediato (erros de configuração/programação)
    e espera+retry (erros transitórios).
    """
    msg = str(exc).lower()

    if any(k in msg for k in _ERROS_CONFIGURACAO):
        raise RuntimeError(
            f"Erro de autenticação/configuração OpenAI (não será reenviado): {exc}"
        ) from exc

    if any(k in msg for k in _ERROS_TRANSITORIOS):
        espera = (2 ** tentativa) * 15
        logger.warning(
            "Rate limit / serviço indisponível. Aguardando %ds... "
            "(tentativa %d/%d)",
            espera, tentativa + 1, max_tentativas,
        )
        _RETRY_SLEEP_FN(espera)
        return

    # Erro desconhecido — re-raise com contexto
    raise RuntimeError(
        f"Erro não esperado da API OpenAI na tentativa {tentativa + 1}: {exc}"
    ) from exc


def _chamar_api(client, prompt: str, max_tokens: int = 16_000) -> str:
    max_tentativas = 4
    for tentativa in range(max_tentativas):
        try:
            resposta = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            return resposta.choices[0].message.content
        except Exception as exc:
            if tentativa == max_tentativas - 1:
                raise RuntimeError(
                    f"Falha após {max_tentativas} tentativas. Último erro: {exc}"
                ) from exc
            _tratar_erro_openai(exc, tentativa, max_tentativas)
    raise RuntimeError("Falha após tentativas (não deve chegar aqui).")


# ---------------------------------------------------------------------------
# HELPERS DE CONTEXTO E REGRAS
# ---------------------------------------------------------------------------

def _bloco_contexto_area(profile: dict) -> str:
    lei = profile.get("lei_exercicio") or "não aplicável"
    normas_reg = (", ".join(profile["normas_regulamentadoras"])
                  if profile["normas_regulamentadoras"] else "não aplicável")
    normas_tec = (", ".join(profile["normas_tecnicas"])
                  if profile["normas_tecnicas"] else "não aplicável")
    return (
        f"ÁREA DE FORMAÇÃO: {profile['nome_area']}\n"
        f"NOME DO PROFISSIONAL FORMADO: {profile['nome_profissional']}\n"
        f"AMBIENTES DE TRABALHO TÍPICOS: {', '.join(profile['ambientes_de_trabalho'])}\n"
        f"EQUIPAMENTOS / MATERIAIS TÍPICOS: {', '.join(profile['equipamentos_tipicos'])}\n"
        f"NORMAS REGULAMENTADORAS APLICÁVEIS: {normas_reg}\n"
        f"NORMAS TÉCNICAS APLICÁVEIS: {normas_tec}\n"
        f"CONSELHO DE CLASSE: {profile['conselho_classe']}\n"
        f"LEI DE EXERCÍCIO PROFISSIONAL: {lei}\n"
        f"GRANDEZAS / PARÂMETROS TÍPICOS: {profile['grandezas_tipicas']}\n"
        f"EPIs / PROTEÇÕES TÍPICAS: {profile['epis_tipicos']}\n"
        f"PROCEDIMENTOS DE SEGURANÇA CHAVE: {profile['procedimentos_seguranca_chave']}\n"
        f"TECNOLOGIAS EMERGENTES: {profile['tecnologias_emergentes']}\n"
        f"SOFTWARES / SISTEMAS TÍPICOS: {profile['softwares_tipicos']}"
    )


def _bloco_regras(profile: dict) -> str:
    lei = profile.get("lei_exercicio") or "não aplicável"
    ambientes = ", ".join(profile["ambientes_de_trabalho"][:4])

    proibido_lista = ""
    if profile.get("vocabulario_proibido"):
        itens = "\n".join(
            f"{i+1}. {t}" for i, t in enumerate(profile["vocabulario_proibido"])
        )
        proibido_lista = (
            "VOCABULÁRIO PROIBIDO — NÃO use em hipótese alguma, "
            "em nenhuma seção, nem como exemplo, nem entre parênteses:\n" + itens
        )

    regras_lista = ""
    if profile.get("regras_terminologia_obrigatorias"):
        itens = "\n".join(
            f"{i+1}. {r}"
            for i, r in enumerate(profile["regras_terminologia_obrigatorias"])
        )
        regras_lista = "TERMINOLOGIA OBRIGATÓRIA — Aplique sem exceção:\n" + itens

    refs_lista = ""
    if profile.get("referencias_oficiais_obrigatorias"):
        itens = "\n".join(
            f"{i+1}. {r}"
            for i, r in enumerate(profile["referencias_oficiais_obrigatorias"])
        )
        refs_lista = (
            "REFERÊNCIAS OFICIAIS QUE DEVEM SER CITADAS quando o tópico permitir:\n"
            + itens
        )

    proibido_inline = ", ".join(profile.get("vocabulario_proibido", []))

    return (
        "======================================================\n"
        "RESTRIÇÕES INVIOLÁVEIS DESTE DOCUMENTO\n"
        "======================================================\n\n"
        f"{proibido_lista}\n\n"
        f"{regras_lista}\n\n"
        f"{refs_lista}\n\n"
        f"A área desta apostila é {profile['nome_area']}.\n"
        f"O profissional formado é {profile['nome_profissional']}.\n"
        f"Os ambientes de trabalho típicos são: {ambientes}.\n"
        f"O conselho de classe é {profile['conselho_classe']}.\n"
        f"A lei de exercício profissional é {lei}.\n\n"
        f"NUNCA mencione nada da lista de vocabulário proibido acima: {proibido_inline}.\n"
        f"Esta é uma apostila de {profile['nome_area']}, NÃO de outra área.\n\n"
        "======================================================"
    )


def _validar_profile(profile: dict, contexto: str = "") -> None:
    if not isinstance(profile, dict) or "nome_area" not in profile:
        raise ValueError(
            f"profile inválido em {contexto}: esperado dict com 'nome_area', "
            f"recebido {type(profile)}"
        )


# ---------------------------------------------------------------------------
# GERADORES DE SEÇÕES GLOBAIS
# ---------------------------------------------------------------------------

def _gerar_introducao(
    client, disciplina: str, ementa: str, contexto: str, profile: dict
) -> str:
    _validar_profile(profile, "_gerar_introducao")
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    ambientes_lista = "\n".join(f"- {a}" for a in profile["ambientes_de_trabalho"])
    normas_reg = (", ".join(profile["normas_regulamentadoras"])
                  if profile["normas_regulamentadoras"] else "não aplicável")
    normas_tec = (", ".join(profile["normas_tecnicas"])
                  if profile["normas_tecnicas"] else "não aplicável")

    prompt = f"""Você é uma IA especialista sênior em geração de apostilas técnicas profissionalizantes para cursos técnicos da área de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a INTRODUÇÃO COMPLETA E EXPANDIDA da disciplina {disciplina} para uma apostila técnica profissional de curso técnico {profile['nome_area']}.

REGRAS OBRIGATÓRIAS:
- O conteúdo deve ter entre 2.500 e 3.500 palavras.
- Use Markdown estruturado: títulos (##, ###), subtítulos, tabelas quando úteis, negrito para conceitos-chave.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Nunca compacte seções. Desenvolva cada bloco com profundidade real.

## Apresentação da Disciplina

Contextualize amplamente a disciplina {disciplina} dentro do curso técnico de {profile['nome_area']} e da formação profissional do {profile['nome_profissional']}. Mínimo de 400 palavras.

## Origem e Evolução Histórica

Trace a história da {disciplina} desde suas origens até o estado atual. Cite marcos e normas que moldaram a disciplina. Mínimo de 600 palavras.

## Relevância para a Prática Profissional

Explique por que esta disciplina é fundamental para o {profile['nome_profissional']} em ambientes como: {', '.join(profile['ambientes_de_trabalho'][:4])}. Mínimo de 500 palavras.

## Integração Curricular e Interdisciplinaridade

Mostre como {disciplina} se conecta com as demais disciplinas do curso técnico de {profile['nome_area']}. Mínimo de 400 palavras.

## O Curso Técnico e o Mercado de Trabalho

Situe {disciplina} no contexto do setor de {profile['nome_area']} com os ambientes:
{ambientes_lista}

Explique como normas ({normas_reg}), normas técnicas ({normas_tec}) e o {profile['conselho_classe']} influenciam a prática. Mínimo de 400 palavras.

## Guia de Estudo e Uso desta Apostila

Descreva o percurso de aprendizagem, as competências desenvolvidas e orientações para aproveitar o material. Mínimo de 300 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16_000)


def _gerar_objetivos(
    client, disciplina: str, ementa: str, contexto: str, profile: dict
) -> str:
    _validar_profile(profile, "_gerar_objetivos")
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    prompt = f"""Você é uma IA especialista sênior em engenharia pedagógica e currículo para cursos técnicos de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere os OBJETIVOS DE APRENDIZAGEM COMPLETOS E DETALHADOS da disciplina {disciplina} para apostila técnica de {profile['nome_area']}.

REGRAS OBRIGATÓRIAS:
- Entre 2.000 e 3.000 palavras.
- Markdown estruturado com tabelas de competências quando útil.
- Linguagem técnica formal em português do Brasil.

## Objetivos Gerais da Disciplina

Apresente 5 objetivos gerais com parágrafo completo para cada. Mínimo de 500 palavras.

## Competências Técnicas a Desenvolver

Apresente 8 competências técnicas práticas para o {profile['nome_profissional']} em ambientes como {', '.join(profile['ambientes_de_trabalho'][:4])}. Mínimo de 600 palavras.

## Competências Cognitivas e de Raciocínio Técnico

5 competências de análise, diagnóstico e resolução de problemas no contexto de {profile['nome_area']}. Mínimo de 400 palavras.

## Competências Atitudinais e Éticas

4 competências atitudinais e éticas inegociáveis no contexto de {profile['nome_area']}. Mínimo de 300 palavras.

## Perfil do Aluno ao Concluir a Disciplina

Descreva o perfil completo com tabela: Competência | Nível Esperado | Aplicação Profissional. Mínimo de 300 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16_000)


def _gerar_exemplos(
    client, disciplina: str, ementa: str, contexto: str, profile: dict
) -> str:
    _validar_profile(profile, "_gerar_exemplos")
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    ambientes = profile["ambientes_de_trabalho"]
    equip = ", ".join(profile["equipamentos_tipicos"][:8])
    casos = ambientes[:5] if len(ambientes) >= 5 else (
        ambientes + ["ambiente de trabalho profissional"] * (5 - len(ambientes))
    )

    prompt = f"""Você é uma IA especialista sênior em produção de material didático para cursos técnicos de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere 5 ESTUDOS DE CASO PRÁTICOS COMENTADOS completos relacionados à disciplina {disciplina} para {profile['nome_area']}.

REGRAS OBRIGATÓRIAS:
- Conteúdo total entre 4.000 e 5.500 palavras.
- Cada caso mínimo de 700 palavras.
- Linguagem técnica formal em português do Brasil.

Os 5 casos devem cobrir contextos distintos:
- Caso 1: {casos[0]}
- Caso 2: {casos[1]}
- Caso 3: {casos[2]}
- Caso 4: {casos[3]}
- Caso 5: {casos[4]}

Equipamentos/materiais: {equip}.

Para cada caso use esta estrutura:
### Caso [N] — [Título]
**Contexto e Descrição do Cenário**
**Análise e Raciocínio Técnico** (parâmetros: {profile['grandezas_tipicas']})
**Conduta e Execução Técnica** (EPIs: {profile['epis_tipicos']})
**Desfecho e Resultado**
**Lição Profissional e Pontos Críticos**
"""
    return _chamar_api(client, prompt, max_tokens=16_000)


def _gerar_resumo(
    client, disciplina: str, ementa: str, contexto: str, profile: dict
) -> str:
    _validar_profile(profile, "_gerar_resumo")
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    ambientes_resumo = ", ".join(profile["ambientes_de_trabalho"][:5])

    prompt = f"""Você é uma IA especialista sênior em produção de material didático técnico para {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere o RESUMO TÉCNICO COMPLETO E EXPANDIDO da disciplina {disciplina} para apostila de {profile['nome_area']}.

REGRAS OBRIGATÓRIAS:
- Entre 2.500 e 3.500 palavras.
- Use Markdown com tabelas, checklists e quadros de revisão.

## Síntese dos Fundamentos Teóricos
Recapitule os conceitos centrais. Mínimo de 600 palavras.

## Síntese das Competências Práticas
Competências, procedimentos e checklist. Mínimo de 600 palavras.

## Pontos Críticos para a Prática Profissional
7 pontos críticos para o {profile['nome_profissional']}. Mínimo de 600 palavras.

## Conexões com o Exercício da Profissão
Relação com a rotina em: {ambientes_resumo}. Mínimo de 400 palavras.

## Glossário Técnico da Disciplina
20 termos técnicos em tabela: Termo | Definição | Contexto de Aplicação. Mínimo de 500 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16_000)


def _gerar_questoes(
    client, disciplina: str, ementa: str, contexto: str, profile: dict
) -> tuple[str, str]:
    """Retorna (bloco_aluno, bloco_professor)."""
    _validar_profile(profile, "_gerar_questoes")
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    grandezas = profile["grandezas_tipicas"]
    nome_prof = profile["nome_profissional"]

    prompt = f"""Você é uma IA especialista sênior em avaliação pedagógica para cursos técnicos de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a AVALIAÇÃO GERAL COMPLETA da disciplina {disciplina} para apostila de {profile['nome_area']}.

INSTRUÇÃO CRÍTICA: Separe a saída em duas partes com esta linha exata:
===CADERNO_PROFESSOR===

Antes do separador: CADERNO DO ALUNO (sem gabaritos).
Após o separador: CADERNO DO PROFESSOR (gabaritos e critérios).

REGRAS: Entre 3.500 e 5.000 palavras total. Markdown estruturado.

CADERNO DO ALUNO:

## Parte I — Questões Objetivas
10 questões Q1–Q10 (múltipla escolha A,B,C,D) sobre {disciplina} em {profile['nome_area']}.

## Parte II — Questões Dissertativas
6 questões DE1–DE6 (conceituais, analíticas, síntese crítica). Apenas enunciados.

## Parte III — Questões Baseadas em Casos Práticos
4 questões CP1–CP4 com cenários completos do {nome_prof}. Apenas enunciados.

===CADERNO_PROFESSOR===

## Gabarito Comentado — Parte I
Alternativa correta e justificativa para cada Q1–Q10.

## Critérios de Avaliação — Parte II
Pontos obrigatórios para DE1–DE6. Mínimo 200 palavras por questão.

## Gabarito e Comentários — Parte III
Resposta completa para CP1–CP4. Mínimo 300 palavras por questão.

## Competências Avaliadas nesta Prova
(Use parâmetros: {grandezas} quando pertinente.)
"""
    resultado = _chamar_api(client, prompt, max_tokens=16_000)
    partes = resultado.split("===CADERNO_PROFESSOR===", 1)
    bloco_aluno = _limpar_vazamentos_prompt(partes[0].strip())
    bloco_professor = (
        _limpar_vazamentos_prompt(partes[1].strip()) if len(partes) > 1 else ""
    )
    return bloco_aluno, bloco_professor


# ---------------------------------------------------------------------------
# FUNÇÃO PÚBLICA: gerar_topico
# ---------------------------------------------------------------------------

def gerar_topico(
    client, disciplina: str, topico: str, contexto: str, profile: dict
) -> str:
    """Gera o conteúdo completo de um tópico para o caderno do aluno."""
    _validar_profile(profile, "gerar_topico")
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    nome_prof = profile["nome_profissional"]
    normas_reg = (", ".join(profile["normas_regulamentadoras"])
                  if profile["normas_regulamentadoras"] else "não aplicável")
    normas_tec = (", ".join(profile["normas_tecnicas"])
                  if profile["normas_tecnicas"] else "não aplicável")
    ambientes_lista = "\n".join(f"- {a}" for a in profile["ambientes_de_trabalho"])
    grandezas = profile["grandezas_tipicas"]

    prompt = f"""Você é uma IA especialista sênior em geração de apostilas técnicas para cursos técnicos de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO COMPLEMENTAR: {contexto}

Gere o conteúdo COMPLETO e EXPANDIDO do tópico "{topico}" da disciplina {disciplina} para apostila técnica de {profile['nome_area']}.

REGRAS EDITORIAIS:
- Entre 5.000 e 7.500 palavras.
- Markdown: títulos (##, ###, ####), tabelas, negrito para conceitos-chave.
- Quadros de atenção: **Atenção:**
- Dicas: **Dica do Técnico:**
- Checklists: - [ ] item
- Linguagem técnica formal em português do Brasil. Sem emojis.

## 1. Abertura do Tópico
Objetivos de aprendizagem (4–6 competências) e contextualização. Mínimo 300 palavras.

## 2. Fundamentação Teórica Aprofundada
Conceitos centrais de {topico}, normas ({normas_reg}, {normas_tec}), parâmetros ({grandezas}). Mínimo 900 palavras.

## 3. Conceitos Fundamentais
Mínimo 6 conceitos com: definição técnica, exemplo prático, erro comum e consequência. Mínimo 800 palavras.

## 4. Aprofundamento Técnico
Situações especiais, critérios de decisão, tecnologias ({profile['tecnologias_emergentes']}), softwares ({profile['softwares_tipicos']}). Mínimo 700 palavras.

## 5. Aplicação Prática Profissional
Uso na rotina do {nome_prof} em pelo menos 3 ambientes:
{ambientes_lista}
Mínimo 800 palavras.

## 6. Procedimentos, Protocolos e Boas Práticas
Checklist passo a passo com EPIs ({profile['epis_tipicos']}), normas ({normas_reg}, {normas_tec}), procedimentos ({profile['procedimentos_seguranca_chave']}). Mínimo 700 palavras.

## 7. Segurança, Ética e Responsabilidade Profissional
Riscos, postura ética, responsabilidade legal ({profile['conselho_classe']}), limites de atuação. Mínimo 500 palavras.

## 8. Estudos de Caso Comentados
2 casos distintos com Cenário, Situação-problema, Dados, Decisão, Conduta, Erro comum, Consequência, Raciocínio, Lição. Mínimo 600 palavras.

## 9. Erros Comuns e Como Evitar
6 erros de profissionais iniciantes: descrição, causas, consequências, prevenção. Mínimo 500 palavras.

## 10. Integração com Outros Tópicos e Disciplinas
Conexões com outras disciplinas do curso de {profile['nome_area']}. Mínimo 300 palavras.

## 11. Resumo Técnico do Tópico
Quadro de Revisão Rápida. Entre 200 e 300 palavras.

## 12. Glossário do Tópico
10 termos técnicos: definição, exemplo de aplicação, cuidado. Mínimo 400 palavras.

## 13. Carreira e Empregabilidade
Como este tópico contribui para a carreira do {nome_prof}, tendências: {profile['tecnologias_emergentes']}. Mínimo 250 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16_000)


# ---------------------------------------------------------------------------
# FUNÇÃO PÚBLICA: gerar_questoes_topico
# ---------------------------------------------------------------------------

def gerar_questoes_topico(
    client, disciplina: str, topico: str, contexto: str, profile: dict
) -> tuple[str, str]:
    """
    Retorna (bloco_aluno, bloco_professor).
    - bloco_aluno: enunciados sem gabaritos.
    - bloco_professor: gabarito + critérios + competências avaliadas.
    """
    _validar_profile(profile, "gerar_questoes_topico")
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    nome_prof = profile["nome_profissional"]
    grandezas = profile["grandezas_tipicas"]

    prompt = f"""Você é uma IA especialista sênior em avaliação pedagógica para cursos técnicos de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a PÁGINA DE PERGUNTAS E EXERCÍCIOS do tópico "{topico}" em {disciplina} para curso técnico de {profile['nome_area']}.

INSTRUÇÃO CRÍTICA: Separe a saída com esta linha exata:
===CADERNO_PROFESSOR===

REGRAS: 500–700 palavras total. Markdown estruturado.

### Questões Objetivas
5 questões Q1–Q5 (A,B,C,D) sobre "{topico}" em {profile['nome_area']}. Enunciados apenas.

### Questões Dissertativas
3 questões D1–D3 exigindo análise e aplicação do {nome_prof}. Enunciados apenas.

### Questões Baseadas em Caso Prático
2 questões CP1–CP2 com cenário realista de "{topico}", exigindo decisão técnica. Enunciados apenas.

===CADERNO_PROFESSOR===

### Gabarito e Critérios de Avaliação
**Gabarito objetivas:** Q1-? | Q2-? | Q3-? | Q4-? | Q5-?
Comentário de cada questão objetiva (por que correta, por que as outras são incorretas).
Critérios para D1–D3 e CP1–CP2.
Competências avaliadas.
(Use parâmetros quando pertinente: {grandezas})
"""
    resultado = _chamar_api(client, prompt, max_tokens=4_000)
    partes = resultado.split("===CADERNO_PROFESSOR===", 1)
    bloco_aluno = _limpar_vazamentos_prompt(partes[0].strip())
    bloco_professor = (
        _limpar_vazamentos_prompt(partes[1].strip()) if len(partes) > 1 else ""
    )
    return bloco_aluno, bloco_professor


# ---------------------------------------------------------------------------
# FUNÇÃO PÚBLICA: gerar_documento
# ---------------------------------------------------------------------------

def gerar_documento(
    client,
    disciplina: str,
    ementa: str,
    conteudo: str,
    contexto: str,
    profile: dict,
) -> str | tuple[str, str]:
    """
    Roteador principal.

    Retorna str para a maioria das seções.
    Retorna tuple(aluno, professor) para questões.

    `profile` deve ser obtido via get_profile() e passado explicitamente.
    Nunca usa variáveis de ambiente para definir a área.
    """
    _validar_profile(profile, "gerar_documento")
    instrucao = conteudo.lower()

    if "introdução" in instrucao or "introducao" in instrucao:
        return _gerar_introducao(client, disciplina, ementa, contexto, profile)
    if "objetivo" in instrucao:
        return _gerar_objetivos(client, disciplina, ementa, contexto, profile)
    # Questões ANTES de exemplos: a instrução de avaliação contém "casos práticos",
    # então "caso" dispararia _gerar_exemplos se testado primeiro.
    if "questão" in instrucao or "dissertat" in instrucao or "avaliação" in instrucao:
        return _gerar_questoes(client, disciplina, ementa, contexto, profile)
    if "exemplo" in instrucao or "caso" in instrucao or "prático" in instrucao:
        return _gerar_exemplos(client, disciplina, ementa, contexto, profile)
    if "resumo" in instrucao or "síntese" in instrucao:
        return _gerar_resumo(client, disciplina, ementa, contexto, profile)

    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)
    prompt = f"""Você é uma IA especialista sênior em produção de material didático para cursos técnicos de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
INSTRUÇÃO: {conteudo}
CONTEXTO: {contexto}

Gere o conteúdo solicitado com entre 2.000 e 3.000 palavras. Use Markdown estruturado.
O conteúdo deve ser orientado para {profile['nome_area']}, com exemplos de
{', '.join(profile['ambientes_de_trabalho'][:3])}, normas
({', '.join(profile['normas_regulamentadoras']) if profile['normas_regulamentadoras'] else 'N/A'})
e situações reais do {profile['nome_profissional']}.
Linguagem técnica formal em português do Brasil. Sem emojis.
"""
    return _chamar_api(client, prompt, max_tokens=16_000)
