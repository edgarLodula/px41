import os
import markdown
import base64
import pdfkit

# CONFIG DO WKHTMLTOPDF
config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')



def gerar_html_completo(conteudos_html, nome_curso, logo_base64):
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">

        <style>
            body {{
                font-family: "Times New Roman", Arial, sans-serif;
                font-size: 12pt;
                line-height: 1.5;
                text-align: justify;
                margin: 3cm 2cm 2cm 3cm;
            }}

            h1 {{
                font-size: 16pt;
                margin-top: 30px;
            }}

            h2 {{
                font-size: 14pt;
                margin-top: 20px;
            }}

            .capa {{
                text-align: center;
                margin-top: 200px;
            }}

            .page-break {{
                page-break-after: always;
            }}
        </style>
    </head>

    <body>

        <!-- CAPA -->
        <div class="capa">
            <img src="data:image/jpeg;base64,{logo_base64}" width="120"><br><br>
            <h1>ESCOLA TÉCNICA SAN MARINO</h1>
            <h2>{nome_curso}</h2>
        </div>

        <div class="page-break"></div>

        <!-- CONTEÚDO -->
        {conteudos_html}

    </body>
    </html>
    """


def gerar_apostilas_por_curso(
    pasta_markdown="data/output/markdown",
    pasta_pdf="data/output/workbooks_pdf",
    logo_path="assets/logo.jpeg"
):
    os.makedirs(pasta_pdf, exist_ok=True)

    # logo → base64
    with open(logo_path, "rb") as img:
        logo_base64 = base64.b64encode(img.read()).decode()

    cursos = os.listdir(pasta_markdown)

    for curso in cursos:
        caminho_curso = os.path.join(pasta_markdown, curso)

        if not os.path.isdir(caminho_curso):
            continue

        print(f"\n📚 Gerando apostila do curso: {curso}")

        conteudos_html = ""

        arquivos_md = sorted(os.listdir(caminho_curso))

        for arquivo in arquivos_md:
            if not arquivo.endswith(".md"):
                continue

            caminho_md = os.path.join(caminho_curso, arquivo)

            with open(caminho_md, "r", encoding="utf-8") as f:
                md_texto = f.read()

            disciplina = arquivo.replace(".md", "").replace("_", " ")

            html = markdown.markdown(md_texto)

            conteudos_html += f"""
                <h1>{disciplina}</h1>
                {html}
                <div class="page-break"></div>
            """

        html_final = gerar_html_completo(conteudos_html, curso, logo_base64)

        nome_pdf = curso.replace(" ", "_") + ".pdf"
        caminho_pdf = os.path.join(pasta_pdf, nome_pdf)

        # ✅ AQUI ESTÁ A CORREÇÃO
        pdfkit.from_string(html_final, caminho_pdf, configuration=config)

        print(f"   ✅ PDF gerado: {caminho_pdf}")