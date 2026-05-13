import os
import time
from openai import OpenAI


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def configurar_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("❌ OPENAI_API_KEY não encontrada no .env.")
    client = OpenAI(api_key=api_key)
    print(f"✅ OpenAI configurado (modelo: {OPENAI_MODEL})")
    return client


def _tratar_erro_openai(erro: str, tentativa: int, max_tentativas: int):
    if "401" in erro or "authentication" in erro.lower() or "invalid_api_key" in erro.lower():
        raise Exception(
            f"❌ Chave OpenAI inválida ou sem permissão. Verifique OPENAI_API_KEY. Detalhe: {erro}"
        )
    elif "429" in erro or "503" in erro or "500" in erro:
        espera = (2 ** tentativa) * 15
        print(f"⚠️ Rate limit/serviço indisponível. Aguardando {espera}s... (tentativa {tentativa + 1}/{max_tentativas})")
        time.sleep(espera)
    else:
        raise


def _chamar_api(client, prompt: str, max_tokens: int = 16000) -> str:
    for tentativa in range(4):
        try:
            resposta = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_tokens,
            )
            return resposta.choices[0].message.content
        except Exception as e:
            _tratar_erro_openai(str(e), tentativa, 4)
    raise Exception("❌ Falha após 4 tentativas.")


# =============================================================================
# GERADORES DE SEÇÕES GLOBAIS DA DISCIPLINA
# =============================================================================

def _gerar_introducao(client, disciplina: str, ementa: str, contexto: str) -> str:
    prompt = f"""Você é uma IA especialista sênior em geração de apostilas técnicas profissionalizantes para cursos técnicos completos.

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a INTRODUÇÃO COMPLETA E EXPANDIDA da disciplina {disciplina} para uma apostila técnica profissional de curso técnico.

REGRAS OBRIGATÓRIAS:
- O conteúdo deve ter entre 2.500 e 3.500 palavras (equivalente a 5 a 7 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), subtítulos, tabelas quando úteis, destaques em negrito para conceitos-chave.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Nunca compacte seções. Desenvolva cada bloco com profundidade real.

Use exatamente esta estrutura:

## Apresentação da Disciplina

Contextualize amplamente a disciplina {disciplina} dentro do curso técnico e da formação profissional. Explique o papel central desta disciplina na construção do perfil do técnico. Mínimo de 400 palavras.

## Origem e Evolução Histórica

Trace a história da {disciplina} desde suas origens até o estado atual do conhecimento. Cite marcos científicos, pesquisadores e eventos que moldaram a disciplina. Explique como as práticas evoluíram e o que mudou no paradigma atual. Mínimo de 600 palavras.

## Relevância para a Prática Profissional

Explique com profundidade por que esta disciplina é fundamental para o técnico em saúde. Mostre o impacto direto no cuidado ao paciente, quais problemas profissionais ela permite resolver e por que um profissional sem esse conhecimento estaria incompleto. Mínimo de 500 palavras.

## Integração Curricular e Interdisciplinaridade

Mostre como {disciplina} se conecta com as demais disciplinas do curso técnico. Identifique conhecimentos prerequisitos, disciplinas que dependem desta e como ela forma uma rede integrada de saberes. Mínimo de 400 palavras.

## O Curso Técnico, o SUS e o Contexto Brasileiro

Situe {disciplina} no contexto do Sistema Único de Saúde, dos hospitais, UBSs e demais serviços de saúde no Brasil. Explique como as políticas públicas, os protocolos do Ministério da Saúde e as realidades locais influenciam a prática desta disciplina. Mínimo de 400 palavras.

## Guia de Estudo e Uso desta Apostila

Descreva o percurso de aprendizagem ao longo da disciplina, as competências que serão desenvolvidas, os principais desafios que o aluno enfrentará e orientações práticas para aproveitar ao máximo o material. Mínimo de 300 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


def _gerar_objetivos(client, disciplina: str, ementa: str, contexto: str) -> str:
    prompt = f"""Você é uma IA especialista sênior em engenharia pedagógica e currículo para cursos técnicos profissionalizantes.

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere os OBJETIVOS DE APRENDIZAGEM COMPLETOS E DETALHADOS da disciplina {disciplina} para uma apostila técnica profissional.

REGRAS OBRIGATÓRIAS:
- O conteúdo deve ter entre 2.000 e 3.000 palavras (equivalente a 4 a 6 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), tabelas de competências quando útil, negrito para objetivos centrais.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.

Use exatamente esta estrutura:

## Objetivos Gerais da Disciplina

Apresente 5 objetivos gerais. Para cada objetivo, escreva um parágrafo completo explicando: o que o aluno deverá ser capaz de fazer ao final, por que este objetivo é importante, como ele se manifesta na prática profissional e qual o nível de profundidade esperado. Mínimo de 500 palavras.

## Competências Técnicas a Desenvolver

Apresente 8 competências técnicas práticas específicas. Para cada competência: explique o que o técnico deverá executar, em quais condições, com qual nível de precisão e autonomia, e quais consequências um erro teria no ambiente clínico. Mínimo de 600 palavras.

## Competências Cognitivas e de Raciocínio Clínico

Apresente 5 competências relacionadas à análise, raciocínio clínico, tomada de decisão e resolução de problemas. Explique como cada habilidade cognitiva se traduz em ações concretas no cotidiano de trabalho. Mínimo de 400 palavras.

## Competências Atitudinais e Éticas

Apresente 4 competências relacionadas a atitudes profissionais, postura ética, comunicação com pacientes e equipe, humanização e responsabilidade. Explique por que cada atitude é inegociável na profissão. Mínimo de 300 palavras.

## Perfil do Aluno ao Concluir a Disciplina

Descreva o perfil completo do aluno ao concluir a disciplina: o que ele saberá, o que saberá fazer e como se comportará profissionalmente. Compare o ponto de partida com o ponto de chegada esperado. Inclua uma tabela de competências com três colunas: Competência | Nível Esperado | Aplicação Profissional. Mínimo de 300 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


def _gerar_exemplos(client, disciplina: str, ementa: str, contexto: str) -> str:
    prompt = f"""Você é uma IA especialista sênior em produção de material didático para cursos técnicos em saúde, com experiência em casos clínicos e situações práticas profissionais.

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere 5 CASOS CLÍNICOS PRÁTICOS COMENTADOS completos e detalhados relacionados à disciplina {disciplina}.

REGRAS OBRIGATÓRIAS:
- O conteúdo total deve ter entre 4.000 e 5.500 palavras (equivalente a 8 a 11 páginas de apostila A4).
- Use Markdown estruturado: títulos de caso (###), subtítulos internos, negrito para pontos críticos, quadros de atenção em negrito.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Cada caso deve ter no mínimo 700 palavras e ser completo e autoexplicativo.

Os 5 casos devem cobrir: hospital de alta complexidade, UBS, UPA/urgência, atendimento domiciliar, ambulatório.
Os perfis de pacientes devem variar: criança, adulto jovem, adulto com comorbidade, idoso, gestante ou paciente crítico.

Para cada caso, use esta estrutura interna:

### Caso [N] — [Título Descritivo da Situação]

**Contexto e Apresentação do Paciente**
Descreva o ambiente, o perfil completo do paciente, como e por que chegou ao serviço, queixa principal, sinais e sintomas observados. Seja específico e realista.

**Avaliação e Raciocínio Técnico**
Descreva o processo de avaliação do técnico: quais dados coleta, como os interpreta, quais hipóteses levanta, como prioriza os problemas e quais protocolos aplica.

**Conduta e Execução Técnica**
Descreva passo a passo as ações do técnico: procedimentos realizados, técnicas utilizadas, equipamentos manuseados, registros feitos e comunicação com a equipe.

**Desfecho e Evolução**
Descreva como o paciente respondeu, os resultados observados, intercorrências e condição ao final do atendimento.

**Lição Profissional e Pontos Críticos**
Explique o que o caso ensina, os erros a evitar, as decisões determinantes e as competências da disciplina {disciplina} diretamente aplicadas.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


def _gerar_resumo(client, disciplina: str, ementa: str, contexto: str) -> str:
    prompt = f"""Você é uma IA especialista sênior em produção de material didático técnico profissionalizante.

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere o RESUMO TÉCNICO COMPLETO E EXPANDIDO da disciplina {disciplina} para apostila técnica profissional.

REGRAS OBRIGATÓRIAS:
- O conteúdo deve ter entre 2.500 e 3.500 palavras (equivalente a 5 a 7 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), tabelas, negrito para pontos críticos.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- O resumo deve consolidar o aprendizado, não substituir o conteúdo dos tópicos.

Use exatamente esta estrutura:

## Síntese dos Fundamentos Teóricos

Recapitule os conceitos teóricos centrais da disciplina, as bases científicas, os mecanismos e os fundamentos que o aluno deve ter dominado. Conecte os conceitos entre si mostrando como formam um corpo coerente de conhecimento. Mínimo de 600 palavras.

## Síntese das Competências Práticas

Recapitule as habilidades técnicas desenvolvidas, os procedimentos aprendidos, os protocolos e como aplicá-los corretamente. Enfatize a execução correta e os erros mais comuns a evitar. Mínimo de 600 palavras.

## Pontos Críticos para a Prática Profissional

Identifique e desenvolva os 7 pontos mais críticos desta disciplina para a atuação do técnico: situações de alto risco, decisões frequentes, competências inegociáveis e conhecimentos que mais impactam a segurança do paciente. Para cada ponto, apresente: descrição, por que é crítico, consequência do erro e boa prática recomendada. Mínimo de 600 palavras.

## Conexões com o Exercício da Profissão

Relacione o aprendizado da disciplina com a rotina real de trabalho em diferentes serviços de saúde. Explique como este conhecimento será utilizado diariamente pelo técnico. Mínimo de 400 palavras.

## Glossário Técnico da Disciplina

Apresente e defina os 20 termos técnicos mais importantes da disciplina {disciplina}. Para cada termo: definição completa, origem do termo quando relevante, contexto de uso e exemplo de aplicação prática. Organize em formato de tabela: Termo | Definição | Contexto de Aplicação. Mínimo de 500 palavras.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


def _gerar_questoes(client, disciplina: str, ementa: str, contexto: str) -> str:
    prompt = f"""Você é uma IA especialista sênior em avaliação pedagógica para cursos técnicos profissionalizantes.

DISCIPLINA: {disciplina}
EMENTA: {ementa}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a AVALIAÇÃO GERAL COMPLETA da disciplina {disciplina} para apostila técnica profissional.

REGRAS OBRIGATÓRIAS:
- O conteúdo total deve ter entre 3.500 e 5.000 palavras (equivalente a 7 a 10 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), numeração clara de questões, negrito para gabaritos e critérios.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- As questões devem avaliar entendimento real, raciocínio e aplicação — não memorização superficial.

Use exatamente esta estrutura:

## Parte I — Questões Objetivas (10 questões)

Crie 10 questões objetivas de múltipla escolha (4 alternativas: A, B, C, D) cobrindo os principais tópicos da disciplina {disciplina}. Cada questão deve avaliar compreensão, aplicação ou análise.

## Gabarito Comentado — Parte I

Para cada questão objetiva: indique a alternativa correta e explique por que é correta e por que as demais são incorretas. Mínimo de 30 palavras por questão.

## Parte II — Questões Dissertativas (6 questões)

Crie 6 questões dissertativas abrangentes que exijam que o aluno explique, analise, relacione e aplique o conhecimento da disciplina {disciplina} em situações profissionais reais. Distribua entre: 2 questões conceituais, 2 questões analíticas, 2 questões de síntese crítica.

Para cada questão dissertativa, inclua imediatamente após o enunciado:
**Critérios de resposta esperada:** [pontos obrigatórios que a resposta deve conter — mínimo 200 palavras por questão]

## Parte III — Questões Baseadas em Casos Práticos (4 questões)

Crie 4 questões baseadas em casos clínicos ou situações profissionais realistas relacionadas a {disciplina}. Cada questão deve apresentar um caso completo e pedir ao aluno que tome decisões, justifique condutas e reflita sobre erros possíveis.

Para cada questão, inclua:
**Gabarito e comentário:** [resposta completa esperada com justificativa técnica — mínimo 300 palavras por questão]

## Competências Avaliadas nesta Prova

Liste todas as competências técnicas, cognitivas e atitudinais avaliadas nas questões acima.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


# =============================================================================
# FUNÇÃO PÚBLICA: gerar_topico
# =============================================================================

def gerar_topico(client, disciplina: str, topico: str, contexto: str) -> str:
    prompt = f"""Você é uma IA especialista sênior em geração de apostilas técnicas profissionalizantes, engenharia pedagógica e produção de material didático para cursos técnicos completos.

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO COMPLEMENTAR: {contexto}

Gere o conteúdo COMPLETO, EXPANDIDO e PROFISSIONAL do tópico "{topico}" da disciplina {disciplina} para apostila técnica de curso técnico.

REGRAS EDITORIAIS OBRIGATÓRIAS:
- O conteúdo deve ter entre 5.000 e 7.500 palavras (equivalente a 10 a 11 páginas de apostila A4).
- Use Markdown estruturado: títulos (##, ###), subtítulos (####), tabelas quando úteis, negrito para conceitos-chave e alertas, quadros de atenção iniciados com **Atenção:**.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- Nunca compacte seções. Desenvolva cada seção com profundidade real e exemplos concretos.
- Nunca use listas sem explicação completa de cada item.
- Nunca entregue definições curtas ou superficiais.

Gere o tópico seguindo EXATAMENTE estas 12 seções obrigatórias:

## 1. Abertura do Tópico

Contextualize o aluno explicando: o que será estudado neste tópico, por que o tema é importante para a formação técnica, onde aparece na atuação profissional do técnico em saúde, quais competências serão desenvolvidas e como o tema se conecta à disciplina {disciplina} e ao curso técnico. Mínimo de 300 palavras. Escreva de forma motivadora e contextualizadora.

## 2. Fundamentação Teórica Aprofundada

Desenvolva o conteúdo do tópico {topico} em profundidade. Inclua: conceitos centrais completamente desenvolvidos, origem e evolução histórica do conceito (quando relevante), fundamentos científicos e técnicos, relação com normas, protocolos ou boas práticas vigentes no Brasil, e implicações para o cotidiano do técnico. Mínimo de 900 palavras. Não use frases genéricas. Não repita ideias para aumentar tamanho. Cada parágrafo deve avançar o raciocínio.

## 3. Conceitos Fundamentais

Para cada conceito central do tópico {topico} (mínimo de 6 conceitos), desenvolva um bloco completo contendo:
- **Definição técnica precisa** do conceito
- Explicação didática acessível para o nível técnico
- Exemplo prático real da aplicação deste conceito
- Erro mais comum relacionado a este conceito
- Consequência profissional desse erro e como preveni-lo

Mínimo de 800 palavras no total desta seção.

## 4. Aprofundamento Técnico

Avance além dos conceitos básicos. Inclua: situações especiais, variações do procedimento ou conceito conforme o contexto clínico, exceções importantes, critérios de decisão do técnico, sinais de alerta que devem ser reconhecidos, limitações da técnica ou abordagem, riscos associados e relação com outros tópicos da disciplina {disciplina}. Mínimo de 700 palavras.

## 5. Aplicação Prática Profissional

Explique detalhadamente como este conteúdo é usado na rotina real de trabalho do técnico. Inclua exemplos concretos em pelo menos 3 contextos distintos e aplicáveis à disciplina {disciplina} (dentre: ambiente hospitalar, UBS, UPA, ambulatório, domicílio, laboratório, gestão, atendimento ao paciente, comunicação com equipe, registro profissional, segurança do paciente). Para cada contexto, descreva: o cenário, as ações do técnico, as decisões tomadas e os resultados esperados. Mínimo de 800 palavras.

## 6. Procedimentos, Protocolos e Boas Práticas

Explique os procedimentos e boas práticas aplicáveis ao tópico {topico}. Inclua: passo a passo conceitual detalhado, cuidados antes da execução, cuidados durante a execução, cuidados após a execução, registros necessários, comunicação com a equipe de saúde, erros que devem ser evitados em cada etapa. Mencione normas e protocolos oficiais vigentes no Brasil (ANVISA, Ministério da Saúde, conselhos profissionais) quando aplicável. Mínimo de 700 palavras.

## 7. Segurança, Ética e Responsabilidade Profissional

Desenvolva os aspectos de segurança e ética relacionados ao tópico {topico}. Inclua: riscos para o profissional técnico, riscos para o paciente ou usuário, riscos institucionais, postura ética exigida, responsabilidade técnica e legal, limites de atuação do técnico de acordo com a legislação vigente, quando e como acionar a supervisão de enfermeiro ou médico, como agir diante de dúvidas ou situações-limite. Mínimo de 500 palavras.

## 8. Casos Práticos Comentados

Apresente 2 casos práticos completos e comentados relacionados ao tópico {topico}. Para cada caso, inclua obrigatoriamente:

**Contexto da situação:** ambiente, perfil do paciente ou usuário, condição apresentada
**Situação-problema:** o desafio real que o técnico enfrenta
**Dados observáveis:** sinais, sintomas, informações disponíveis
**Decisão esperada do técnico:** o que deve ser feito
**Conduta correta detalhada:** passo a passo das ações corretas
**Erro comum nessa situação:** o que os técnicos iniciantes costumam fazer errado
**Consequência do erro:** impacto para o paciente, para o profissional e para a instituição
**Raciocínio explicado:** por que a conduta correta é correta
**Lição profissional:** aprendizado central deste caso

Os dois casos devem abordar situações distintas e complementares do tópico. Mínimo de 600 palavras no total.

## 9. Erros Comuns e Como Evitar

Liste e desenvolva os 6 principais erros cometidos por técnicos iniciantes relacionados ao tópico {topico}. Para cada erro: descreva o erro com precisão, explique por que ele acontece (causas), mostre a consequência profissional real, indique a forma correta de evitar e conecte com a prática profissional real. Mínimo de 500 palavras.

## 10. Integração com Outros Tópicos e Disciplinas

Explique como o tópico {topico} se conecta com: tópicos anteriores e posteriores da disciplina {disciplina}, outras disciplinas do curso técnico, competências profissionais do técnico em saúde, e situações reais de trabalho que exigem integração de conhecimentos de múltiplas áreas. Mínimo de 300 palavras.

## 11. Resumo Técnico do Tópico

Faça um resumo técnico útil e objetivo consolidando os pontos mais críticos do aprendizado. O resumo deve reforçar os conceitos centrais, as condutas corretas e os erros a evitar. Deve ter entre 200 e 300 palavras. Nunca deve substituir o conteúdo das seções anteriores.

## 12. Glossário do Tópico

Inclua os 10 principais termos técnicos do tópico {topico}. Para cada termo, desenvolva:
- **Definição técnica precisa**
- Explicação didática simples
- Exemplo de aplicação prática no contexto profissional
- Cuidado ou erro comum relacionado ao uso ou aplicação deste termo

Organize em blocos por termo. Mínimo de 400 palavras no total desta seção.
"""
    return _chamar_api(client, prompt, max_tokens=16000)


# =============================================================================
# FUNÇÃO PÚBLICA: gerar_questoes_topico
# =============================================================================

def gerar_questoes_topico(client, disciplina: str, topico: str, contexto: str) -> str:
    prompt = f"""Você é uma IA especialista sênior em avaliação pedagógica para cursos técnicos profissionalizantes.

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO COMPLEMENTAR: {contexto}

Gere a PÁGINA DE PERGUNTAS, EXERCÍCIOS E GABARITO do tópico "{topico}" na disciplina {disciplina}.

REGRAS OBRIGATÓRIAS:
- Esta seção deve ter entre 500 e 700 palavras (equivalente a 1 página de apostila A4).
- Use Markdown estruturado: títulos (###), numeração clara, negrito para gabaritos e critérios.
- Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
- As perguntas devem avaliar entendimento real e aplicação — não memorização superficial.
- Seja preciso e objetivo. Não ultrapasse 700 palavras.

Use exatamente esta estrutura:

### Questoes Objetivas

Crie 5 questoes objetivas de multipla escolha (alternativas A, B, C, D) sobre o topico {topico}. Cada questao deve avaliar compreensao, aplicacao ou analise — nao apenas memorização.

Q1. [Enunciado]
A) [opcao]  B) [opcao]  C) [opcao]  D) [opcao]

Q2. [Enunciado]
A) [opcao]  B) [opcao]  C) [opcao]  D) [opcao]

Q3. [Enunciado]
A) [opcao]  B) [opcao]  C) [opcao]  D) [opcao]

Q4. [Enunciado]
A) [opcao]  B) [opcao]  C) [opcao]  D) [opcao]

Q5. [Enunciado]
A) [opcao]  B) [opcao]  C) [opcao]  D) [opcao]

### Questoes Dissertativas

Crie 3 questoes dissertativas que exijam analise e aplicacao do conhecimento do topico {topico} em situacoes profissionais reais.

D1. [Enunciado completo]

D2. [Enunciado completo]

D3. [Enunciado completo]

### Questoes Baseadas em Caso Pratico

Crie 2 questoes baseadas em casos praticos realistas do topico {topico}. Cada questao deve apresentar uma situacao real e pedir ao aluno que tome uma decisao e explique a conduta.

CP1. [Caso e enunciado]

CP2. [Caso e enunciado]

### Gabarito e Criterios de Avaliacao

**Gabarito objetivas:** Q1-[letra] | Q2-[letra] | Q3-[letra] | Q4-[letra] | Q5-[letra]

**Comentario das respostas objetivas:** Para cada questao, explique brevemente por que a alternativa correta e correta e por que as demais estao incorretas.

**Criterios das dissertativas e casos praticos:** Para cada questao (D1, D2, D3, CP1, CP2), liste os pontos essenciais que a resposta deve conter.

**Competencias avaliadas:** [lista das competencias tecnicas e atitudinais avaliadas nesta pagina]
"""
    return _chamar_api(client, prompt, max_tokens=4000)


# =============================================================================
# FUNÇÃO PÚBLICA: gerar_documento (mantém a assinatura original)
# =============================================================================

def gerar_documento(client, disciplina: str, ementa: str, conteudo: str, contexto: str) -> str:
    instrucao = conteudo.lower()

    if "introdução" in instrucao or "introducao" in instrucao or "introdução" in instrucao:
        return _gerar_introducao(client, disciplina, ementa, contexto)
    elif "objetivo" in instrucao:
        return _gerar_objetivos(client, disciplina, ementa, contexto)
    elif "exemplo" in instrucao or "caso" in instrucao or "prático" in instrucao:
        return _gerar_exemplos(client, disciplina, ementa, contexto)
    elif "resumo" in instrucao or "síntese" in instrucao:
        return _gerar_resumo(client, disciplina, ementa, contexto)
    elif "questão" in instrucao or "quest" in instrucao or "dissertat" in instrucao or "avaliação" in instrucao:
        return _gerar_questoes(client, disciplina, ementa, contexto)
    else:
        prompt = f"""Você é uma IA especialista sênior em produção de material didático para cursos técnicos profissionalizantes.

DISCIPLINA: {disciplina}
EMENTA: {ementa}
INSTRUÇÃO: {conteudo}
CONTEXTO: {contexto}

Gere o conteúdo solicitado com entre 2.000 e 3.000 palavras. Use Markdown estruturado com títulos e subtítulos.
Linguagem técnica formal em português do Brasil. Sem emojis. Sem linguagem informal.
"""
        return _chamar_api(client, prompt, max_tokens=16000)
