import os
import time
from openai import OpenAI

from src.content_generation.area_profiles import get_profile

import re

_PADROES_PROMPT_VAZADO = [
    re.compile(r"^\s*(Crie|Gere|Elabore|Produza|Escreva)\s+\d+\s+quest[õo]es.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*TAREFAS DE GERAÇÃO.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*T\d+\.\s+(Gere|Crie|Elabore|Produza|Escreva).*$", re.IGNORECASE | re.MULTILINE),
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


OPENAI_MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# Define a área de formação: "industrial", "saude", "enfermagem", etc.
# Altere no .env: AREA_FORMACAO=saude
AREA_FORMACAO = os.getenv("AREA_FORMACAO", "industrial")


def configurar_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY não encontrada no .env.")
    client = OpenAI(api_key=api_key)
    print(f"OpenAI configurado (modelo: {OPENAI_MODEL})")
    return client


def _tratar_erro_openai(erro: str, tentativa: int, max_tentativas: int):
    if "401" in erro or "authentication" in erro.lower() or "invalid_api_key" in erro.lower():
        raise Exception(
            f"Chave OpenAI inválida ou sem permissão. Verifique OPENAI_API_KEY. Detalhe: {erro}"
        )
    elif "429" in erro or "503" in erro or "500" in erro:
        espera = (2 ** tentativa) * 15
        print(f"Rate limit/serviço indisponível. Aguardando {espera}s... (tentativa {tentativa + 1}/{max_tentativas})")
        time.sleep(espera)
    else:
        raise


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


# =============================================================================
# HELPERS DE CONTEXTO E REGRAS
# =============================================================================

def _bloco_contexto_area(profile: dict) -> str:
    lei = profile.get("lei_exercicio") or "não aplicável"
    return f"""ÁREA DE FORMAÇÃO: {profile['nome_area']}
NOME DO PROFISSIONAL FORMADO: {profile['nome_profissional']}
AMBIENTES DE TRABALHO TÍPICOS: {', '.join(profile['ambientes_de_trabalho'])}
EQUIPAMENTOS / MATERIAIS TÍPICOS: {', '.join(profile['equipamentos_tipicos'])}
NORMAS REGULAMENTADORAS APLICÁVEIS: {', '.join(profile['normas_regulamentadoras'])}
NORMAS TÉCNICAS APLICÁVEIS: {', '.join(profile['normas_tecnicas'])}
CONSELHO DE CLASSE: {profile['conselho_classe']}
LEI DE EXERCÍCIO PROFISSIONAL: {lei}
GRANDEZAS / PARÂMETROS TÍPICOS: {profile['grandezas_tipicas']}
EPIs / PROTEÇÕES TÍPICAS: {profile['epis_tipicos']}
PROCEDIMENTOS DE SEGURANÇA CHAVE: {profile['procedimentos_seguranca_chave']}
TECNOLOGIAS EMERGENTES: {profile['tecnologias_emergentes']}
SOFTWARES / SISTEMAS TÍPICOS: {profile['softwares_tipicos']}"""


def _bloco_regras(profile: dict) -> str:
    lei = profile.get("lei_exercicio") or "não aplicável"
    ambientes = ", ".join(profile["ambientes_de_trabalho"][:4])

    proibido_lista = ""
    if profile.get("vocabulario_proibido"):
        itens = "\n".join(f"{i+1}. {t}" for i, t in enumerate(profile["vocabulario_proibido"]))
        proibido_lista = f"VOCABULÁRIO PROIBIDO — NÃO use em hipótese alguma, em nenhuma seção, nem como exemplo, nem entre parênteses:\n{itens}"

    regras_lista = ""
    if profile.get("regras_terminologia_obrigatorias"):
        itens = "\n".join(f"{i+1}. {r}" for i, r in enumerate(profile["regras_terminologia_obrigatorias"]))
        regras_lista = f"TERMINOLOGIA OBRIGATÓRIA — Aplique sem exceção:\n{itens}"

    refs_lista = ""
    if profile.get("referencias_oficiais_obrigatorias"):
        itens = "\n".join(f"{i+1}. {r}" for i, r in enumerate(profile["referencias_oficiais_obrigatorias"]))
        refs_lista = f"REFERÊNCIAS OFICIAIS QUE DEVEM SER CITADAS quando o tópico permitir:\n{itens}"

    proibido_inline = ", ".join(profile.get("vocabulario_proibido", []))

    return f"""======================================================
RESTRIÇÕES INVIOLÁVEIS DESTE DOCUMENTO
======================================================

Se você violar qualquer item desta lista, o documento é REJEITADO automaticamente.

{proibido_lista}

{regras_lista}

{refs_lista}

A área desta apostila é {profile['nome_area']}.
O profissional formado é {profile['nome_profissional']}.
Os ambientes de trabalho típicos são: {ambientes}.
O conselho de classe é {profile['conselho_classe']}.
A lei de exercício profissional é {lei}.

NUNCA mencione nada da lista de vocabulário proibido acima: {proibido_inline}.
Esta é uma apostila de {profile['nome_area']}, NÃO de engenharia industrial.

======================================================"""


# =============================================================================
# GERADORES DE SEÇÕES GLOBAIS DA DISCIPLINA
# =============================================================================

def _gerar_introducao(client, disciplina, ementa, contexto, profile):
    profile = get_profile(os.getenv("AREA_FORMACAO", "industrial"))
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    ambientes_lista = "\n".join(f"- {a}" for a in profile["ambientes_de_trabalho"])
    normas_reg = ", ".join(profile["normas_regulamentadoras"])
    normas_tec = ", ".join(profile["normas_tecnicas"])

    prompt = f"""Você é uma IA especialista sênior em geração de apostilas técnicas profissionalizantes para cursos técnicos da área de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a INTRODUÇÃO COMPLETA E EXPANDIDA da disciplina {disciplina} para uma apostila técnica profissional de curso técnico {profile['nome_area']}.

REGRAS OBRIGATÓRIAS:
- O conteúdo deve ter entre 2.500 e 3.500 palavras (equivalente a 5 a 7 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), subtítulos, tabelas quando úteis, negrito para conceitos-chave.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Nunca compacte seções. Desenvolva cada bloco com profundidade real.
- Use segmentação visual: divida o texto em microseções com subtítulos claros; evite blocos corridos de mais de 4 parágrafos sem um subtítulo ou elemento visual (tabela, quadro ou lista comentada).
- Onde pertinente, insira marcadores de figura no formato **[FIGURA: descrição detalhada do diagrama ou imagem sugerida]** para indicar onde imagens devem ser inseridas na apostila impressa.

Use exatamente esta estrutura:

## Apresentação da Disciplina

Contextualize amplamente a disciplina {disciplina} dentro do curso técnico de {profile['nome_area']} e da formação profissional. Explique o papel central desta disciplina na construção do perfil do {profile['nome_profissional']}. Mínimo de 400 palavras.

## Origem e Evolução Histórica

Trace a história da {disciplina} desde suas origens até o estado atual do conhecimento técnico-profissional. Cite marcos, pesquisadores, normas e eventos que moldaram a disciplina. Explique como as práticas na área de {profile['nome_area']} evoluíram e o que mudou no paradigma atual. Mínimo de 600 palavras.

## Relevância para a Prática Profissional

Explique com profundidade por que esta disciplina é fundamental para o {profile['nome_profissional']}. Mostre o impacto direto na atuação em ambientes como: {', '.join(profile['ambientes_de_trabalho'][:4])}. Quais problemas profissionais ela permite resolver e por que um profissional sem esse conhecimento estaria incompleto para atuar no mercado. Mínimo de 500 palavras.

## Integração Curricular e Interdisciplinaridade

Mostre como {disciplina} se conecta com as demais disciplinas do curso técnico de {profile['nome_area']}. Identifique conhecimentos pré-requisitos, disciplinas que dependem desta e como ela forma uma rede integrada de saberes técnicos. Mínimo de 400 palavras.

## O Curso Técnico e o Mercado de Trabalho

Situe {disciplina} no contexto do setor de {profile['nome_area']}, abordando os principais ambientes de atuação:
{ambientes_lista}

Explique como normas regulamentadoras ({normas_reg}), normas técnicas ({normas_tec}), exigências do {profile['conselho_classe']} e as demandas do mercado influenciam a prática desta disciplina. Mínimo de 400 palavras.

## Guia de Estudo e Uso desta Apostila

Descreva o percurso de aprendizagem ao longo da disciplina, as competências que serão desenvolvidas, os principais desafios que o aluno enfrentará e orientações práticas para aproveitar ao máximo o material. Mínimo de 300 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


def _gerar_objetivos(client, disciplina: str, ementa: str, contexto: str) -> str:
    profile = get_profile(os.getenv("AREA_FORMACAO", "industrial"))
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    prompt = f"""Você é uma IA especialista sênior em engenharia pedagógica e currículo para cursos técnicos profissionalizantes da área de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere os OBJETIVOS DE APRENDIZAGEM COMPLETOS E DETALHADOS da disciplina {disciplina} para uma apostila técnica profissional de curso técnico de {profile['nome_area']}.

REGRAS OBRIGATÓRIAS:
- O conteúdo deve ter entre 2.000 e 3.000 palavras (equivalente a 4 a 6 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), tabelas de competências quando útil, negrito para objetivos centrais.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Use segmentação visual: evite blocos corridos; insira subtítulos, quadros ou tabelas para organizar o conteúdo.

Use exatamente esta estrutura:

## Objetivos Gerais da Disciplina

Apresente 5 objetivos gerais. Para cada objetivo, escreva um parágrafo completo explicando: o que o aluno deverá ser capaz de fazer ao final, por que este objetivo é importante para a atuação do {profile['nome_profissional']}, como ele se manifesta na prática profissional e qual o nível de profundidade esperado. Mínimo de 500 palavras.

## Competências Técnicas a Desenvolver

Apresente 8 competências técnicas práticas específicas para o {profile['nome_profissional']}. Para cada competência: explique o que o profissional deverá executar, em quais condições e ambientes de trabalho ({', '.join(profile['ambientes_de_trabalho'][:4])}), com qual nível de precisão e autonomia, e quais consequências um erro teria no ambiente de trabalho (segurança, qualidade do atendimento/serviço, danos a equipamentos). Mínimo de 600 palavras.

## Competências Cognitivas e de Raciocínio Técnico

Apresente 5 competências relacionadas à análise técnica, raciocínio lógico, diagnóstico de situações, tomada de decisão e resolução de problemas no contexto de {profile['nome_area']}. Explique como cada habilidade cognitiva se traduz em ações concretas no cotidiano do {profile['nome_profissional']}. Mínimo de 400 palavras.

## Competências Atitudinais e Éticas

Apresente 4 competências relacionadas a atitudes profissionais, postura ética, comunicação com colegas e supervisores, responsabilidade com segurança e conservação do patrimônio. Explique por que cada atitude é inegociável no contexto de {profile['nome_area']}. Mínimo de 300 palavras.

## Perfil do Aluno ao Concluir a Disciplina

Descreva o perfil completo do aluno ao concluir a disciplina: o que ele saberá, o que saberá fazer e como se comportará profissionalmente. Compare o ponto de partida com o ponto de chegada esperado. Inclua uma tabela de competências com três colunas: Competência | Nível Esperado | Aplicação Profissional. Mínimo de 300 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


def _gerar_exemplos(client, disciplina: str, ementa: str, contexto: str) -> str:
    profile = get_profile(os.getenv("AREA_FORMACAO", "industrial"))
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    ambientes = profile["ambientes_de_trabalho"]
    equip = ", ".join(profile["equipamentos_tipicos"][:8])
    # Garante 5 casos com ambientes do perfil
    casos = ambientes[:5] if len(ambientes) >= 5 else ambientes + ["ambiente de trabalho profissional"] * (5 - len(ambientes))

    prompt = f"""Você é uma IA especialista sênior em produção de material didático para cursos técnicos de {profile['nome_area']}, com experiência em estudos de caso profissionais e situações práticas reais.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere 5 ESTUDOS DE CASO PRÁTICOS COMENTADOS completos e detalhados relacionados à disciplina {disciplina} para o contexto de {profile['nome_area']}.

REGRAS OBRIGATÓRIAS:
- O conteúdo total deve ter entre 4.000 e 5.500 palavras (equivalente a 8 a 11 páginas de apostila A4).
- Use Markdown estruturado: títulos de caso (###), subtítulos internos, negrito para pontos críticos, quadros de atenção em negrito.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Cada caso deve ter no mínimo 700 palavras e ser completo e autoexplicativo.
- Onde pertinente, insira marcadores **[FIGURA: descrição do diagrama, fluxograma ou esquema sugerido]** indicando onde imagens devem entrar.

Os 5 estudos de caso devem cobrir contextos distintos da área de {profile['nome_area']}:
- Caso 1: {casos[0]}
- Caso 2: {casos[1]}
- Caso 3: {casos[2]}
- Caso 4: {casos[3]}
- Caso 5: {casos[4]}

Os perfis de equipamentos/materiais e situações devem variar: {equip} ou outros pertinentes à disciplina.

Para cada caso, use esta estrutura interna:

### Caso [N] — [Título Descritivo da Situação]

**Contexto e Descrição do Cenário**
Descreva o ambiente de trabalho, o equipamento ou situação envolvida, a condição que originou a necessidade de intervenção, os sinais/sintomas observados e as condições presentes. Seja específico e realista.

**Análise e Raciocínio Técnico**
Descreva o processo de avaliação do {profile['nome_profissional']}: quais dados coleta (medições, parâmetros: {profile['grandezas_tipicas']}), como os interpreta, quais hipóteses levanta, como prioriza as ações e quais normas ou procedimentos aplica ({', '.join(profile['normas_regulamentadoras'])}).

**Conduta e Execução Técnica**
Descreva passo a passo as ações do {profile['nome_profissional']}: procedimentos realizados, materiais e instrumentos utilizados, EPIs ({profile['epis_tipicos']}) e medidas de segurança adotadas ({profile['procedimentos_seguranca_chave']}), registros feitos e comunicação com a equipe.

**Desfecho e Resultado**
Descreva como a situação evoluiu, os resultados pós-intervenção, eventuais intercorrências e o estado final após o atendimento.

**Lição Profissional e Pontos Críticos**
Explique o que o caso ensina, os erros a evitar, as decisões determinantes e as competências da disciplina {disciplina} diretamente aplicadas.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


def _gerar_resumo(client, disciplina: str, ementa: str, contexto: str) -> str:
    profile = get_profile(os.getenv("AREA_FORMACAO", "industrial"))
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    ambientes_resumo = ", ".join(profile["ambientes_de_trabalho"][:5])

    prompt = f"""Você é uma IA especialista sênior em produção de material didático técnico profissionalizante para a área de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere o RESUMO TÉCNICO COMPLETO E EXPANDIDO da disciplina {disciplina} para apostila técnica profissional de curso técnico de {profile['nome_area']}.

REGRAS OBRIGATÓRIAS:
- O conteúdo deve ter entre 2.500 e 3.500 palavras (equivalente a 5 a 7 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), tabelas, negrito para pontos críticos.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- O resumo deve consolidar o aprendizado, não substituir o conteúdo dos tópicos.
- Use segmentação visual: insira quadros de revisão rápida, checklists e tabelas para organizar os pontos críticos.

Use exatamente esta estrutura:

## Síntese dos Fundamentos Teóricos

Recapitule os conceitos teóricos centrais da disciplina, as bases científicas e técnicas, os princípios de funcionamento e os fundamentos que o aluno deve ter dominado. Conecte os conceitos entre si mostrando como formam um corpo coerente de conhecimento técnico. Mínimo de 600 palavras.

## Síntese das Competências Práticas

Recapitule as habilidades técnicas desenvolvidas, os procedimentos aprendidos, os protocolos da área de {profile['nome_area']} e como aplicá-los corretamente. Enfatize a execução correta e os erros mais comuns a evitar. Inclua um checklist das principais competências práticas. Mínimo de 600 palavras.

## Pontos Críticos para a Prática Profissional

Identifique e desenvolva os 7 pontos mais críticos desta disciplina para a atuação do {profile['nome_profissional']}: situações de alto risco, decisões frequentes no campo, competências inegociáveis e conhecimentos que mais impactam a segurança, a qualidade do serviço e os resultados profissionais. Para cada ponto, apresente: descrição, por que é crítico, consequência do erro e boa prática recomendada. Mínimo de 600 palavras.

## Conexões com o Exercício da Profissão

Relacione o aprendizado da disciplina com a rotina real de trabalho do {profile['nome_profissional']} em diferentes ambientes: {ambientes_resumo}. Explique como este conhecimento será utilizado diariamente. Mínimo de 400 palavras.

## Glossário Técnico da Disciplina

Apresente e defina os 20 termos técnicos mais importantes da disciplina {disciplina}. Para cada termo: definição completa, origem do termo quando relevante, contexto de uso na área de {profile['nome_area']} e exemplo de aplicação prática. Organize em formato de tabela: Termo | Definição | Contexto de Aplicação. Mínimo de 500 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


def _gerar_questoes(client, disciplina: str, ementa: str, contexto: str) -> tuple:
    """Retorna (bloco_aluno, bloco_professor). Usa separador ===CADERNO_PROFESSOR=== na saída do LLM."""
    profile = get_profile(os.getenv("AREA_FORMACAO", "industrial"))
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    grandezas = profile["grandezas_tipicas"]
    nome_prof = profile["nome_profissional"]

    prompt = f"""Você é uma IA especialista sênior em avaliação pedagógica para cursos técnicos profissionalizantes da área de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a AVALIAÇÃO GERAL COMPLETA da disciplina {disciplina} para apostila técnica profissional de curso técnico de {profile['nome_area']}.

INSTRUÇÃO CRÍTICA DE FORMATAÇÃO: Você DEVE separar a saída em duas partes com a linha exata abaixo (sem espaços extras, exatamente assim):
===CADERNO_PROFESSOR===

Tudo ANTES do separador é o CADERNO DO ALUNO (apenas enunciados, sem gabaritos ou critérios).
Tudo DEPOIS do separador é o CADERNO DO PROFESSOR (gabaritos, critérios e competências).

REGRAS OBRIGATÓRIAS:
- Conteúdo total entre 3.500 e 5.000 palavras (equivalente a 7 a 10 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), numeração clara de questões.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- As questões devem avaliar entendimento real, raciocínio técnico e aplicação, não memorização superficial.
- Onde pertinente, inclua questões com parâmetros numéricos ({grandezas}) exigindo interpretação ou cálculo.

CADERNO DO ALUNO — gere as três partes abaixo (sem gabaritos, sem critérios):

============================================================
TAREFAS DE GERAÇÃO (NÃO reproduza estas linhas no output):

T1. Gere 10 questões objetivas de múltipla escolha (A, B, C, D) cobrindo os principais tópicos de {disciplina}, avaliando compreensão, aplicação e análise técnica no contexto de {profile['nome_area']}.
T2. Gere 6 questões dissertativas em situações profissionais reais do {nome_prof}: 2 conceituais, 2 analíticas, 2 de síntese crítica. Apenas enunciados.
T3. Gere 4 questões de caso prático com cenários completos exigindo decisão técnica, justificativa e reflexão sobre erros. Apenas enunciados.
============================================================

FORMATO DE SAÍDA — reproduza APENAS as seções abaixo, substituindo cada <...>. NÃO inclua as TAREFAS acima, NÃO escreva "Crie X questões", NÃO repita este aviso:

## Parte I — Questões Objetivas

Q1. <enunciado>
A) <opção>  B) <opção>  C) <opção>  D) <opção>

[... repita Q2 a Q10 no mesmo formato]

## Parte II — Questões Dissertativas

DE1. <enunciado conceitual>
DE2. <enunciado conceitual>
DE3. <enunciado analítico>
DE4. <enunciado analítico>
DE5. <enunciado de síntese crítica>
DE6. <enunciado de síntese crítica>

## Parte III — Questões Baseadas em Casos Práticos

CP1. <cenário completo e pergunta>
CP2. <cenário completo e pergunta>
CP3. <cenário completo e pergunta>
CP4. <cenário completo e pergunta>
===CADERNO_PROFESSOR===

## Gabarito Comentado — Parte I

Para cada questão objetiva: indique a alternativa correta e explique por que é correta e por que as demais são incorretas. Mínimo de 30 palavras por questão.

## Critérios de Avaliação — Parte II

Para cada questão dissertativa (DE1 a DE6): liste os pontos obrigatórios que a resposta deve conter. Mínimo de 200 palavras de critérios por questão.

## Gabarito e Comentários — Parte III

Para cada questão de caso prático (CP1 a CP4): resposta completa esperada com justificativa técnica. Mínimo de 300 palavras por questão.

## Competências Avaliadas nesta Prova

Liste todas as competências técnicas, cognitivas e atitudinais avaliadas nas questões acima.
"""
    resultado = _chamar_api(client, prompt, max_tokens=16000)
    partes = resultado.split("===CADERNO_PROFESSOR===", 1)
    bloco_aluno = _limpar_vazamentos_prompt(partes[0].strip())
    bloco_professor = _limpar_vazamentos_prompt(partes[1].strip()) if len(partes) > 1 else ""
    return bloco_aluno, bloco_professor


# =============================================================================
# FUNÇÃO PÚBLICA: gerar_topico
# =============================================================================

def gerar_topico(client, disciplina: str, topico: str, contexto: str) -> str:
    profile = get_profile(os.getenv("AREA_FORMACAO", "industrial"))
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    nome_prof = profile["nome_profissional"]
    normas_reg = ", ".join(profile["normas_regulamentadoras"])
    normas_tec = ", ".join(profile["normas_tecnicas"])
    ambientes_lista = "\n".join(f"- {a}" for a in profile["ambientes_de_trabalho"])
    grandezas = profile["grandezas_tipicas"]

    prompt = f"""Você é uma IA especialista sênior em geração de apostilas técnicas profissionalizantes, engenharia pedagógica e produção de material didático para cursos técnicos da área de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO COMPLEMENTAR: {contexto}

Gere o conteúdo COMPLETO, EXPANDIDO e PROFISSIONAL do tópico "{topico}" da disciplina {disciplina} para apostila técnica de curso técnico de {profile['nome_area']}.

REGRAS EDITORIAIS OBRIGATÓRIAS:
- O conteúdo deve ter entre 5.000 e 7.500 palavras (equivalente a 10 a 15 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), subtítulos (####), tabelas quando úteis, negrito para conceitos-chave e alertas.
- Quadros de atenção iniciados com **Atenção:** para riscos e advertências.
- Dicas do profissional iniciadas com **Dica do Técnico:** para boas práticas e atalhos profissionais.
- Checklists em formato de lista marcada (- [ ] item) para procedimentos e verificações.
- Revisões rápidas ao final de cada seção de fundamentos: **Revisão Rápida:** [resumo em 2–3 linhas].
- Marcadores de figura no formato **[FIGURA: descrição detalhada do diagrama, esquema, fluxograma ou imagem sugerida]** indicando onde imagens devem ser inseridas.
- Onde pertinente, apresente fórmulas ou parâmetros de referência com comentário das variáveis e um exemplo resolvido passo a passo.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Nunca compacte seções. Desenvolva cada seção com profundidade real e exemplos concretos.
- Nunca use listas sem explicação completa de cada item.
- Nunca entregue definições curtas ou superficiais.

Gere o tópico seguindo EXATAMENTE estas 13 seções obrigatórias:

## 1. Abertura do Tópico

Inicie com um bloco de **Objetivos de Aprendizagem** listando de 4 a 6 competências que o aluno desenvolverá neste tópico (formato de lista marcada). Em seguida, contextualize o aluno explicando: o que será estudado neste tópico, por que o tema é importante para a formação do {nome_prof}, onde aparece na atuação profissional, quais competências serão desenvolvidas e como o tema se conecta à disciplina {disciplina} e ao curso técnico. Mínimo de 300 palavras. Escreva de forma motivadora e contextualizadora.

## 2. Fundamentação Teórica Aprofundada

Desenvolva o conteúdo do tópico {topico} em profundidade. Inclua: conceitos centrais completamente desenvolvidos, origem e evolução histórica do conceito (quando relevante), fundamentos científicos e técnicos, relação com normas regulamentadoras ({normas_reg}) e normas técnicas ({normas_tec}) vigentes, e implicações para o cotidiano do {nome_prof}. Onde pertinente, apresente fórmulas ou parâmetros de referência ({grandezas}) com descrição das variáveis e exemplo resolvido. Mínimo de 900 palavras. Não use frases genéricas. Cada parágrafo deve avançar o raciocínio.

## 3. Conceitos Fundamentais

Para cada conceito central do tópico {topico} (mínimo de 6 conceitos), desenvolva um bloco completo contendo:
- **Definição técnica precisa** do conceito
- Explicação didática acessível para o nível técnico
- Exemplo prático real da aplicação deste conceito em ambiente de {profile['nome_area']}
- Erro mais comum relacionado a este conceito
- Consequência profissional desse erro e como preveni-lo

Mínimo de 800 palavras no total desta seção.

## 4. Aprofundamento Técnico

Avance além dos conceitos básicos. Inclua: situações especiais, variações do procedimento ou conceito conforme o contexto profissional, exceções importantes, critérios de decisão do {nome_prof}, sinais de alerta que devem ser reconhecidos, limitações da técnica ou abordagem, riscos associados e relação com outros tópicos da disciplina {disciplina}.

Quando pertinente ao tópico, aborde tecnologias e sistemas da área de {profile['nome_area']}: {profile['tecnologias_emergentes']}; parâmetros típicos ({grandezas}); softwares e sistemas usados ({profile['softwares_tipicos']}); procedimentos e protocolos de segurança ({profile['procedimentos_seguranca_chave']}). Mínimo de 700 palavras.

## 5. Aplicação Prática Profissional

Explique detalhadamente como este conteúdo é usado na rotina real de trabalho do {nome_prof}. Inclua exemplos concretos em pelo menos 3 ambientes distintos, dentre:
{ambientes_lista}

Para cada contexto, descreva: o cenário, as ações do {nome_prof}, as decisões tomadas e os resultados esperados. Mínimo de 800 palavras.

## 6. Procedimentos, Protocolos e Boas Práticas

Explique os procedimentos e boas práticas aplicáveis ao tópico {topico}. Inclua um checklist passo a passo (use formato - [ ] item) cobrindo: preparação antes da execução (verificações, EPIs: {profile['epis_tipicos']}), procedimento durante a execução, verificações após a execução, registros necessários e comunicação com a equipe. Mencione normas regulamentadoras ({normas_reg}) e normas técnicas ({normas_tec}) quando aplicável ao tópico. Referencie os procedimentos de segurança chave: {profile['procedimentos_seguranca_chave']}. Mínimo de 700 palavras.

## 7. Segurança, Ética e Responsabilidade Profissional

Desenvolva os aspectos de segurança e ética relacionados ao tópico {topico}. Inclua: riscos para o profissional (biológicos, físicos, químicos, ergonômicos conforme o tópico e o perfil de {profile['nome_area']}), riscos para equipamentos/materiais/instalações, riscos ao serviço e ao patrimônio, postura ética exigida, responsabilidade técnica e legal (incluindo {profile['conselho_classe']}), limites de atuação do {nome_prof} e quando acionar o responsável técnico ou superior, como agir diante de dúvidas ou situações-limite. Mínimo de 500 palavras.

## 8. Estudos de Caso Comentados

Apresente 2 estudos de caso completos e comentados relacionados ao tópico {topico} no contexto de {profile['nome_area']}. Os dois casos devem abordar situações distintas e complementares. Para cada caso, inclua obrigatoriamente:

**Cenário:** ambiente, equipamento ou situação envolvida, condição apresentada
**Situação-problema:** o desafio técnico real que o {nome_prof} enfrenta
**Dados observáveis:** parâmetros, leituras, sintomas, informações disponíveis
**Decisão esperada do técnico:** o que deve ser feito
**Conduta correta detalhada:** passo a passo das ações corretas, com EPIs e segurança
**Erro comum nessa situação:** o que os profissionais iniciantes costumam fazer errado
**Consequência do erro:** impacto para o serviço, para a segurança e para o profissional
**Raciocínio explicado:** por que a conduta correta é correta
**Lição profissional:** aprendizado central deste caso

Mínimo de 600 palavras no total.

## 9. Erros Comuns e Como Evitar

Liste e desenvolva os 6 principais erros cometidos por profissionais iniciantes relacionados ao tópico {topico}. Para cada erro: descreva o erro com precisão, explique por que ele acontece (causas), mostre a consequência profissional real, indique a forma correta de evitar e conecte com a prática profissional real. Mínimo de 500 palavras.

## 10. Integração com Outros Tópicos e Disciplinas

Explique como o tópico {topico} se conecta com: tópicos anteriores e posteriores da disciplina {disciplina}, outras disciplinas do curso técnico de {profile['nome_area']}, competências profissionais do {nome_prof} e situações reais de trabalho que exigem integração de conhecimentos de múltiplas áreas técnicas. Mínimo de 300 palavras.

## 11. Resumo Técnico do Tópico

Faça um resumo técnico útil e objetivo consolidando os pontos mais críticos do aprendizado. Inclua um quadro de **Revisão Rápida** com os conceitos centrais, as condutas corretas e os erros a evitar. Deve ter entre 200 e 300 palavras. Nunca deve substituir o conteúdo das seções anteriores.

## 12. Glossário do Tópico

Inclua os 10 principais termos técnicos do tópico {topico}. Para cada termo, desenvolva:
- **Definição técnica precisa**
- Explicação didática simples
- Exemplo de aplicação prática no contexto de {profile['nome_area']}
- Cuidado ou erro comum relacionado ao uso ou aplicação deste termo

Organize em blocos por termo. Mínimo de 400 palavras no total desta seção.

## 13. Carreira e Empregabilidade

Explique como o domínio deste tópico contribui para a carreira do {nome_prof}. Aborde: principais segmentos e ambientes que demandam esta competência ({', '.join(profile['ambientes_de_trabalho'][:4])}), funções e cargos que utilizam este conhecimento diretamente, certificações e habilitações relevantes ({normas_reg}, {profile['conselho_classe']}), dicas para destacar esta competência no currículo e em entrevistas técnicas, e tendências do mercado relacionadas ao tópico: {profile['tecnologias_emergentes']}. Mínimo de 250 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


# =============================================================================
# FUNÇÃO PÚBLICA: gerar_questoes_topico
# =============================================================================

def gerar_questoes_topico(client, disciplina: str, topico: str, contexto: str) -> tuple:
    """
    Retorna (bloco_aluno, bloco_professor).
    - bloco_aluno: apenas Questões Objetivas, Dissertativas e Casos Práticos (enunciados).
    - bloco_professor: Gabarito + Comentários + Critérios + Competências avaliadas.
    """
    profile = get_profile(os.getenv("AREA_FORMACAO", "industrial"))
    ctx = _bloco_contexto_area(profile)
    regras = _bloco_regras(profile)

    nome_prof = profile["nome_profissional"]
    grandezas = profile["grandezas_tipicas"]

    prompt = f"""Você é uma IA especialista sênior em avaliação pedagógica para cursos técnicos profissionalizantes da área de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a PÁGINA DE PERGUNTAS E EXERCÍCIOS do tópico "{topico}" na disciplina {disciplina} para curso técnico de {profile['nome_area']}.

INSTRUÇÃO CRÍTICA DE FORMATAÇÃO: Você DEVE separar a saída em duas partes com a linha exata abaixo (sem espaços extras):
===CADERNO_PROFESSOR===

Tudo ANTES do separador é o CADERNO DO ALUNO (apenas enunciados, sem respostas).
Tudo DEPOIS do separador é o CADERNO DO PROFESSOR (gabarito e critérios completos).

REGRAS OBRIGATÓRIAS:
- Total entre 500 e 700 palavras.
- Use Markdown estruturado: títulos (###), numeração clara.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- As perguntas devem avaliar entendimento real e aplicação técnica, não memorização superficial.
- Onde pertinente, inclua questões com parâmetros numéricos ({grandezas}) exigindo interpretação ou cálculo.

============================================================
TAREFAS DE GERAÇÃO (NÃO reproduza estas linhas no output. Elas são instruções para você, não conteúdo da apostila):

T1. Gere 5 questões objetivas de múltipla escolha (alternativas A, B, C, D) sobre "{topico}" no contexto de {profile['nome_area']}. Cada questão deve avaliar compreensão, aplicação ou análise técnica — nunca memorização. Variar o nível de complexidade.

T2. Gere 3 questões dissertativas exigindo análise e aplicação do conhecimento de "{topico}" em situações profissionais reais do {nome_prof}.

T3. Gere 2 questões de caso prático com cenário realista de "{topico}" na área de {profile['nome_area']}, exigindo decisão técnica justificada e descrição da conduta correta.
============================================================

FORMATO DE SAÍDA EXATO — reproduza APENAS o que está abaixo, substituindo cada marcador <...> pelo conteúdo gerado. NÃO inclua as linhas de TAREFAS acima, NÃO inclua frases como "Crie X questões", NÃO inclua o cabeçalho "TAREFAS" nem este aviso:

### Questões Objetivas

Q1. <enunciado da questão objetiva>
A) <opção A>  B) <opção B>  C) <opção C>  D) <opção D>

Q2. <enunciado>
A) <opção A>  B) <opção B>  C) <opção C>  D) <opção D>

Q3. <enunciado>
A) <opção A>  B) <opção B>  C) <opção C>  D) <opção D>

Q4. <enunciado>
A) <opção A>  B) <opção B>  C) <opção C>  D) <opção D>

Q5. <enunciado>
A) <opção A>  B) <opção B>  C) <opção C>  D) <opção D>

### Questões Dissertativas

D1. <enunciado completo da dissertativa>

D2. <enunciado completo>

D3. <enunciado completo>

### Questões Baseadas em Caso Prático

CP1. <cenário detalhado e pergunta exigindo decisão técnica>

CP2. <cenário detalhado e pergunta exigindo decisão técnica>

===CADERNO_PROFESSOR===

### Gabarito e Critérios de Avaliação

**Gabarito objetivas:** Q1-<letra> | Q2-<letra> | Q3-<letra> | Q4-<letra> | Q5-<letra>

**Comentário das respostas objetivas:** Para cada questão, explique por que a alternativa correta está correta e por que as demais estão incorretas.

**Critérios das dissertativas e casos práticos:** Para cada questão (D1, D2, D3, CP1, CP2), liste os pontos essenciais que a resposta deve conter.

**Competências avaliadas:** Lista das competências técnicas e atitudinais avaliadas nesta página.
"""
    resultado = _chamar_api(client, prompt, max_tokens=4000)
    partes = resultado.split("===CADERNO_PROFESSOR===", 1)
    bloco_aluno = _limpar_vazamentos_prompt(partes[0].strip())
    bloco_professor = _limpar_vazamentos_prompt(partes[1].strip()) if len(partes) > 1 else ""
    return bloco_aluno, bloco_professor


# =============================================================================
# FUNÇÃO PÚBLICA: gerar_documento (mantém a assinatura original)
# =============================================================================

def gerar_documento(client, disciplina, ementa, conteudo, contexto, profile):
    instrucao = conteudo.lower()

    if "introdução" in instrucao or "introducao" in instrucao:
        return _gerar_introducao(client, disciplina, ementa, contexto, profile)
    elif "objetivo" in instrucao:
        return _gerar_objetivos(client, disciplina, ementa, contexto, profile)
    elif "exemplo" in instrucao or "caso" in instrucao or "prático" in instrucao:
        return _gerar_exemplos(client, disciplina, ementa, contexto, profile)
    elif "resumo" in instrucao or "síntese" in instrucao:
        return _gerar_resumo(client, disciplina, ementa, contexto, profile)
    elif "questão" in instrucao or "dissertat" in instrucao or "avaliação" in instrucao:
        return _gerar_questoes(client, disciplina, ementa, contexto, profile)
    else:
        ctx = _bloco_contexto_area(profile)
        regras = _bloco_regras(profile)
        prompt = f"""Você é uma IA especialista sênior em produção de material didático para cursos técnicos profissionalizantes da área de {profile['nome_area']}.

{ctx}

{regras}

DISCIPLINA: {disciplina}
EMENTA: {ementa}
INSTRUÇÃO: {conteudo}
CONTEXTO: {contexto}

Gere o conteúdo solicitado com entre 2.000 e 3.000 palavras. Use Markdown estruturado com títulos e subtítulos.
O conteúdo deve ser orientado para o contexto de {profile['nome_area']}, com exemplos de {', '.join(profile['ambientes_de_trabalho'][:3])}, normas ({', '.join(profile['normas_regulamentadoras'])}) e situações reais de trabalho do {profile['nome_profissional']}.
Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
"""
        return _chamar_api(client, prompt, max_tokens=16000)
