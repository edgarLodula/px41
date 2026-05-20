"""
Diagnostico de extracao de PDF — mostra o que o pdfplumber consegue extrair.
Execute com: python scripts/diagnostico_pdf.py
"""
import sys
import pdfplumber

PDFS = [
    "data/input/Tecnico em Administracao - Ementa e Conteudo Programatico.docx.pdf",
    "data/input/Tabela_Completa_Conteudo_Programatico_Tecnico_Enfermagem.docx.pdf",
]

# Tenta achar o PDF correto mesmo com acento no nome
import os, glob
arquivos = glob.glob("data/input/*.pdf")
if not arquivos:
    print("Nenhum PDF encontrado em data/input/")
    sys.exit(1)

print("PDFs encontrados:")
for i, a in enumerate(arquivos):
    print(f"  [{i}] {os.path.basename(a)}")

escolha = input("\nQual PDF analisar? [numero]: ").strip()
caminho = arquivos[int(escolha)]
print(f"\nAnalisando: {caminho}\n{'='*60}")

with pdfplumber.open(caminho) as pdf:
    print(f"Total de paginas: {len(pdf.pages)}\n")

    for i, pagina in enumerate(pdf.pages[:5]):  # primeiras 5 paginas
        print(f"\n--- PAGINA {i+1} ---")

        # Tabelas
        tabelas = pagina.extract_tables() or []
        print(f"  Tabelas encontradas: {len(tabelas)}")
        for t_idx, tabela in enumerate(tabelas[:2]):
            print(f"  Tabela {t_idx+1}: {len(tabela)} linhas")
            for linha in tabela[:3]:
                print(f"    {linha}")
            if len(tabela) > 3:
                print(f"    ... +{len(tabela)-3} linhas")

        # Texto
        texto = pagina.extract_text() or ""
        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        print(f"  Linhas de texto: {len(linhas)}")
        for linha in linhas[:8]:
            print(f"    {linha[:100]}")
        if len(linhas) > 8:
            print(f"    ... +{len(linhas)-8} linhas")
