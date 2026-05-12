import pdfplumber
import csv
import os

def extrair_pdf_para_csv(caminho_pdf: str, caminho_csv: str):
    os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)

    registros = []
    with pdfplumber.open(caminho_pdf) as pdf:
        nome_curso = pdf.pages[0].extract_text().split("\n")[0].strip()
        for pagina in pdf.pages:
            for tabela in (pagina.extract_tables() or []):
                for linha in tabela:
                    if not linha[0] or not linha[2]:
                        continue
                    if linha[0].strip() == "Disciplina":
                        continue
                    registros.append({
                        "Curso":                 nome_curso,
                        "Disciplina":            linha[0].strip(),
                        "Ementa":                (linha[1] or "").strip(),
                        "Conteudo_Programatico": " | ".join(
                            c.strip() for c in (linha[2] or "").split("\n") if c.strip()
                        )
                    })

    with open(caminho_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Curso", "Disciplina", "Ementa", "Conteudo_Programatico"])
        writer.writeheader()
        writer.writerows(registros)

    print(f"✅ CSV salvo em: {caminho_csv} ({len(registros)} registros)")