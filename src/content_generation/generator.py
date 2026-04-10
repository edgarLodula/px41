import google.generativeai as genai
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

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 8192
        }
    )

    print("✅ Gemini configurado")
    return model


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
def gerar_documento(model, disciplina, ementa, conteudo, contexto):
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

    for tentativa in range(5):
        try:
            resposta = model.generate_content(prompt)
            return resposta.text

        except Exception as e:
            erro = str(e)

            if "429" in erro or "503" in erro:
                espera = (2 ** tentativa) * 10
                print(f"⚠️ Aguardando {espera}s...")
                time.sleep(espera)
            else:
                raise

    raise Exception(f"❌ Falha ao gerar conteúdo para {disciplina}")