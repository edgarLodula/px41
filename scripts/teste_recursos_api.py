"""
Script de diagnóstico — verifica imports e configuração da API.
Execute com: python test_api.py
"""
import sys

print("=" * 60)
print("DIAGNÓSTICO DA API")
print("=" * 60)

# 1. FastAPI básico
print("\n[1] FastAPI...")
try:
    from fastapi import FastAPI
    app_test = FastAPI()
    print(f"    OK — docs_url: {app_test.docs_url}")
    print(f"    OK — openapi_url: {app_test.openapi_url}")
except Exception as e:
    print(f"    ERRO: {e}")

# 2. Imports do pipeline
print("\n[2] Imports do pipeline...")
imports = [
    ("pdf_processor",       "src.syllabus_extractor.pdf_processor",        ["processar_pdf", "processar_semantico"]),
    ("data_loader",         "src.content_generation.data_loader",           ["carregar_base"]),
    ("embedding_model",     "src.content_generation.embedding_model",       ["carregar_modelo", "gerar_embeddings"]),
    ("faiss_index",         "src.content_generation.faiss_index",           ["criar_ou_carregar_index"]),
    ("rag_pipeline",        "src.content_generation.rag_pipeline",          ["buscar_chunks"]),
    ("generator",           "src.content_generation.generator",             ["configurar_gemini", "gerar_documento"]),
    ("markdown_generator",  "src.output_formatter.markdown_generator",      ["gerar_markdowns"]),
    ("workbooks_generator", "src.workbooks_generator.workbooks_generator",  ["gerar_apostilas_por_curso"]),
    ("pipeline_video",      "src.video_generator.pipeline_video",           ["gerar_videos_por_disciplina"]),
]

erros = []
for nome, modulo, funcoes in imports:
    try:
        mod = __import__(modulo, fromlist=funcoes)
        print(f"    OK  — {nome}")
    except Exception as e:
        print(f"    ERRO — {nome}: {e}")
        erros.append((nome, str(e)))

# 3. Importar api.py completo
print("\n[3] Importando api.py...")
try:
    import api
    print(f"    OK — rotas registradas:")
    for route in api.app.routes:
        if hasattr(route, "methods"):
            print(f"         {list(route.methods)} {route.path}")
except Exception as e:
    print(f"    ERRO: {e}")

# 4. Variáveis de ambiente
print("\n[4] Variáveis de ambiente...")
from dotenv import load_dotenv
import os
load_dotenv()
vars_necessarias = ["GEMINI_API_KEY", "GEMINI_MODEL", "HEYGEN_API_KEY", "HEYGEN_AVATAR_ID", "HEYGEN_VOICE_ID"]
for var in vars_necessarias:
    val = os.getenv(var)
    status = "OK" if val else "AUSENTE"
    print(f"    {status} — {var}")

print("\n" + "=" * 60)
if erros:
    print(f"RESUMO: {len(erros)} erro(s) encontrado(s)")
    for nome, e in erros:
        print(f"  - {nome}: {e}")
else:
    print("RESUMO: todos os imports OK")
print("=" * 60)
