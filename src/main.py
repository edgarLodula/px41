import os
import json
from pdf_processor import processar_pdf, processar_semantico

PASTA_PDFS = "data/input"
PASTA_SAIDA = "data/output"

os.makedirs(PASTA_SAIDA, exist_ok=True)

arquivos_pdf = [f for f in os.listdir(PASTA_PDFS) if f.endswith(".pdf")]

base_geral = []

for arquivo in arquivos_pdf:
    caminho_pdf = os.path.join(PASTA_PDFS, arquivo)

    print(f"Processando: {arquivo}")

    paginas = processar_pdf(caminho_pdf)
    base_ia = processar_semantico(paginas, arquivo)

    base_geral.extend(base_ia)

caminho_json = os.path.join(PASTA_SAIDA, "base_geral.json")

with open(caminho_json, "w", encoding="utf-8") as f:
    json.dump(base_geral, f, ensure_ascii=False, indent=2)

print("Finalizado")