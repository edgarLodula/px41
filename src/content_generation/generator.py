import os
import time
from google import genai
from google.genai import types



SYSTEM_PROMPT = """
Você é um especialista em educação técnica e elaboração de apostilas profissionais para cursos técnicos de saúde no Brasil.

REGRA ABSOLUTA E INVIOLÁVEL:
Todo o conteúdo gerado deve ser EXCLUSIVAMENTE sobre a disciplina, ementa e tópicos informados abaixo.
É terminantemente proibido introduzir temas, exemplos ou conceitos que não estejam diretamente relacionados à ementa fornecida.
Se a ementa fala sobre comunicação, APENAS comunicação deve aparecer. Se fala sobre anatomia, APENAS anatomia.

QUALIDADE OBRIGATÓRIA:
- Cada seção deve ser densa, técnica e aprofundada, equivalente a um capítulo de apostila universitária
- Desenvolva raciocínio progressivo: do contexto histórico à aplicação prática
- Explique sempre o PORQUÊ, o COMO e o PARA QUE de cada conceito
- Cada parágrafo deve introduzir uma informação NOVA — é proibido reformular ou repetir ideias já escritas
- Linguagem formal, técnica e instrutiva em português do Brasil
- Exemplos aplicados ao contexto real de um técnico em saúde

FORMATO OBRIGATÓRIO:
Retorne APENAS texto corrido, sem markdown, sem símbolos como #, *, -, sem listas com marcadores.
Separe cada seção com o rótulo exato abaixo, seguido de dois pontos e quebra de linha:

INTRODUCAO:
Contexto histórico da disciplina, relevância na formação técnica, aplicação prática no cotidiano profissional e importância dentro do curso.

OBJETIVOS:
Objetivos gerais e específicos da disciplina, focados em competências técnicas, cognitivas e atitudinais que o aluno deve desenvolver.

TOPICOS:
Desenvolva TODOS os tópicos da ementa com profundidade máxima.
Cada tópico deve funcionar como um subcapítulo de livro técnico: contexto, fundamentação teórica, mecanismos, aplicação prática e implicações clínicas ou profissionais reais.
Nunca repita informações já mencionadas em tópicos anteriores.

EXEMPLOS:
Mínimo de 3 exemplos práticos detalhados, contextualizados no ambiente real de trabalho do técnico.
Cada exemplo deve ter situação, desenvolvimento e conclusão clara.

RESUMO:
Síntese objetiva dos principais conceitos abordados, destacando as competências desenvolvidas e os pontos mais relevantes para a prática profissional.

QUESTOES:
8 questões variadas: 3 conceituais, 3 analíticas e 2 aplicadas a situações reais.
Cada questão deve exigir raciocínio crítico, não apenas memorização.
"""


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def configurar_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("❌ GEMINI_API_KEY não encontrada.")

    client = genai.Client(api_key=api_key)
    print(f"✅ Gemini configurado (modelo: {GEMINI_MODEL})")
    return client


def gerar_documento(client, disciplina, ementa, conteudo, contexto):
    prompt = f"""{SYSTEM_PROMPT}

--- DISCIPLINA ---
{disciplina}

Ementa:
{ementa}

Conteúdo:
{conteudo}

--- CONTEXTO ADICIONAL ---
{contexto}

Gere o material:
"""
    for tentativa in range(4):
        try:
            resposta = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=32000,
                )
            )
            return resposta.text
        except Exception as e:
            erro = str(e)
            if "403" in erro or "PERMISSION_DENIED" in erro:
                raise Exception(
                    f"❌ Acesso negado à Gemini API (403). Verifique se o projeto Google Cloud "
                    f"tem a API habilitada e se a chave GEMINI_API_KEY está correta. Detalhe: {erro}"
                )
            elif "503" in erro or "429" in erro:
                espera = (2 ** tentativa) * 15
                print(f"⚠️ Aguardando {espera}s... (tentativa {tentativa + 1}/4)")
                time.sleep(espera)
            else:
                raise
    raise Exception(f"❌ Falha ao gerar documento: {disciplina}")


    

def gerar_topico(client, disciplina, topico, contexto):
    prompt = f"""
Você é um especialista em educação técnica e elaboração de apostilas para cursos técnicos de saúde no Brasil.

REGRA ABSOLUTA:
Gere conteúdo EXCLUSIVAMENTE sobre o tópico abaixo, dentro do contexto da disciplina informada.
Não introduza temas externos. Não repita ideias — cada parágrafo deve avançar o raciocínio com informação nova.

DISCIPLINA: {disciplina}
TÓPICO: {topico}
CONTEXTO: {contexto}

REQUISITOS OBRIGATÓRIOS:
- Mínimo de 2500 palavras
- Estrutura progressiva: contexto histórico → fundamentação teórica → aplicação prática → implicações reais
- Explique o PORQUÊ, o COMO e o PARA QUE de cada conceito apresentado
- Inclua conexões com a prática do técnico em enfermagem no dia a dia
- Linguagem formal, técnica e instrutiva, nível de manual universitário
- Texto corrido, sem markdown, sem símbolos como #, *, -, sem listas com marcadores
- Cada parágrafo deve ser denso e substantivo — sem frases de preenchimento ou repetições

Desenvolva o conteúdo completo agora, indo direto ao tema:
"""
    for tentativa in range(4):
        try:
            resposta = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=10000,
                )
            )
            return resposta.text
        except Exception as e:
            erro = str(e)
            if "403" in erro or "PERMISSION_DENIED" in erro:
                raise Exception(
                    f"❌ Acesso negado à Gemini API (403). Verifique se o projeto Google Cloud "
                    f"tem a API habilitada e se a chave GEMINI_API_KEY está correta. Detalhe: {erro}"
                )
            elif "503" in erro or "429" in erro:
                espera = (2 ** tentativa) * 15
                print(f"⚠️ Rate limit/serviço indisponível. Aguardando {espera}s... (tentativa {tentativa + 1}/4)")
                time.sleep(espera)
            else:
                raise
    raise Exception(f"❌ Falha ao gerar tópico '{topico}' após 4 tentativas.")

