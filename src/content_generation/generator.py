from google import genai
from google.genai import types
import os
import time

# -------------------------------
# CONFIGURAÇÃO DO GEMINI
# -------------------------------
def configurar_gemini():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise Exception(
            "❌ GEMINI_API_KEY não encontrada.\n"
            "Use: set GEMINI_API_KEY=sua_chave"
        )

    client = genai.Client(api_key=api_key)
    print("✅ Gemini configurado")
    return client

# -------------------------------
# PROMPT BASE
# -------------------------------
SYSTEM_PROMPT = """
Você é um especialista em educação técnica e criação de material didático.
Receberá a ementa e o conteúdo programático de uma disciplina e deverá
gerar um documento de estudo completo e aprofundado, em português do Brasil.

O documento deve conter:
1. Introdução à disciplina
2. Objetivos de aprendizagem
3. Explicação dos tópicos
4. Exemplos práticos
5. Resumo
6. 5 questões dissertativas

Seja didático, claro e detalhado.
"""

# -------------------------------
# GERAÇÃO DE CONTEÚDO
# -------------------------------
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

    for tentativa in range(3):
        try:
            resposta = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                )
            )
            return resposta.text

        except Exception as e:
            erro = str(e)

            if "429" in erro or "503" in erro:
                espera = (2 ** tentativa) * 2
                print(f"⚠️ Aguardando {espera}s...")
                time.sleep(espera)
            else:
                raise

    raise Exception(f"❌ Falha ao gerar conteúdo para {disciplina}")