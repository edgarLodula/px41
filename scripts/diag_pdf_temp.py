import pdfplumber, sys, glob, os

# Tenta o caminho com acento primeiro, depois sem
caminhos = [
    "C:/Users/lizan/Downloads/Técnico em Administração - Ementa e Conteúdo Programático.docx.pdf",
    "C:/Users/lizan/Downloads/Tecnico em Administracao - Ementa e Conteudo Programatico.docx.pdf",
]
caminhos += glob.glob("C:/Users/lizan/Downloads/*.pdf")

caminho = None
for c in caminhos:
    if os.path.exists(c):
        caminho = c
        break

if not caminho:
    print("PDF nao encontrado. PDFs em Downloads:")
    for f in glob.glob("C:/Users/lizan/Downloads/*.pdf"):
        print(f"  {f}")
    sys.exit(1)

print(f"Analisando: {os.path.basename(caminho)}")

with pdfplumber.open(caminho) as pdf:
    print(f"Total de paginas: {len(pdf.pages)}")
    for i, p in enumerate(pdf.pages[:3]):
        print(f"\n=== PAGINA {i+1} ===")
        tabelas = p.extract_tables() or []
        print(f"Tabelas encontradas: {len(tabelas)}")
        for ti, t in enumerate(tabelas[:2]):
            print(f"  Tabela {ti+1} ({len(t)} linhas x {len(t[0]) if t else 0} colunas):")
            for linha in t[:4]:
                print(f"    {linha}")
        texto = p.extract_text() or ""
        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        print(f"Linhas de texto: {len(linhas)}")
        for l in linhas[:8]:
            print(f"  {l[:120]}")
