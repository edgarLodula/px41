import os
import re
import shutil
import tempfile
import markdown
import base64
import pdfkit

_WKHTMLTOPDF_PATHS = [
    r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
    r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    "/usr/local/bin/wkhtmltopdf",
    "/usr/bin/wkhtmltopdf",
]

def _get_pdfkit_config():
    for path in _WKHTMLTOPDF_PATHS:
        if os.path.exists(path):
            return pdfkit.configuration(wkhtmltopdf=path)
    try:
        return pdfkit.configuration()
    except OSError:
        raise OSError(
            "wkhtmltopdf não encontrado. Instale em https://wkhtmltopdf.org/downloads.html "
            f"ou defina o caminho em _WKHTMLTOPDF_PATHS. Caminhos tentados: {_WKHTMLTOPDF_PATHS}"
        )

WKHTMLTOPDF_OPTIONS = {
    "encoding": "UTF-8",
    "page-size": "A4",
    "margin-top": "2.5cm",
    "margin-right": "2cm",
    "margin-bottom": "2.5cm",
    "margin-left": "2.5cm",
    "footer-center": "[page]",
    "footer-font-size": "9",
    "footer-spacing": "5",
    "enable-local-file-access": "",
    "no-stop-slow-scripts": "",
    "javascript-delay": "200",
}

MD_EXTENSIONS = [
    "tables",
    "fenced_code",
    "nl2br",
    "sane_lists",
    "attr_list",
]


# ---------------------------------------------------------------------------
# PÓS-PROCESSAMENTO DO HTML GERADO PELO MARKDOWN
# ---------------------------------------------------------------------------

def _pos_processar_html(html: str) -> str:
    """Aplica classes CSS específicas a blocos semanticamente identificáveis."""

    # Questões objetivas: Q1. … Q2. … até Q10.
    html = re.sub(
        r'(<p>)(Q\d{1,2}\.\s)',
        r'<p class="questao-objetiva"><span class="questao-num">\2</span>',
        html
    )

    # Alternativas A) B) C) D) em parágrafos próprios
    html = re.sub(
        r'(<p>)([A-D]\))',
        r'<p class="alternativa">\2',
        html
    )

    # Questões dissertativas D1. D2. D3.
    html = re.sub(
        r'(<p>)(D\d\.\s)',
        r'<p class="questao-dissertativa"><span class="questao-num">\2</span>',
        html
    )

    # Casos práticos CP1. CP2.
    html = re.sub(
        r'(<p>)(CP\d\.\s)',
        r'<p class="questao-caso"><span class="questao-num">\2</span>',
        html
    )

    # Blocos de gabarito: parágrafos que começam com "Gabarito"
    html = re.sub(
        r'(<p>)(Gabarito\s*(?:das\s*\w+)?:?\s)',
        r'<p class="gabarito"><strong>\2</strong>',
        html
    )

    # Critérios das dissertativas
    html = re.sub(
        r'(<p>)(Crit[eé]rios?\s)',
        r'<p class="criterios"><strong>\2</strong>',
        html
    )

    # Controle editorial — envolve a tabela seguinte num bloco especial
    html = re.sub(
        r'(<p><strong>Controle Editorial)',
        r'<div class="controle-editorial"><p><strong>Controle Editorial',
        html
    )
    # Fecha o bloco após a primeira tabela que seguir
    html = re.sub(
        r'(</table>)(\s*</div class="controle-editorial">)?',
        r'\1</div>',
        html,
        count=0
    )

    # Rótulos de campos em casos práticos: **Contexto:**, **Conduta:**, etc.
    html = re.sub(
        r'<strong>(Contexto\s|Situação-problema|Dados\s|Decisão\s|Conduta\s|Desfecho\s|Raciocínio\s|Lição\s|Erro\s)',
        r'<strong class="campo-caso">\1',
        html
    )

    return html



# ---------------------------------------------------------------------------
# TEMPLATE HTML COMPLETO
# ---------------------------------------------------------------------------

def gerar_html_completo(conteudos_html, nome_curso, logo_base64, nome_disciplina=None, subtitulo_capa=None):
    nome_curso_display = nome_curso.replace("_", " ")
    nome_disciplina_display = nome_disciplina.replace("_", " ") if nome_disciplina else nome_curso_display
    subtitulo_display = subtitulo_capa or f"Material Didático — {nome_curso_display}"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <style>
        /* =====================================================================
           RESET E BASE
        ===================================================================== */
        * {{ box-sizing: border-box; }}

        body {{
            font-family: "Arial", "Helvetica Neue", sans-serif;
            font-size: 11.5pt;
            line-height: 1.65;
            color: #1a1a1a;
            margin: 0;
            padding: 0;
        }}

        /* =====================================================================
           HIERARQUIA DE TÍTULOS
        ===================================================================== */

        /* Título da disciplina (gerado pelo loop) */
        h1.titulo-disciplina {{
            font-size: 22pt;
            color: #0d2f5e;
            border-bottom: 4px solid #0d2f5e;
            padding-bottom: 8px;
            margin-top: 0;
            margin-bottom: 6px;
        }}

        /* Seções principais: Introdução, Objetivos, Tópicos, Resumo… */
        h2 {{
            font-size: 16pt;
            color: #1a4a8a;
            border-bottom: 2px solid #1a4a8a;
            padding-bottom: 4px;
            margin-top: 28px;
            margin-bottom: 8px;
            page-break-after: avoid;
        }}

        /* Nome do tópico: ### Tópico 1: … */
        h3 {{
            font-size: 13.5pt;
            color: #0d2f5e;
            background-color: #eef4fb;
            border-left: 5px solid #1a4a8a;
            padding: 6px 10px;
            margin-top: 24px;
            margin-bottom: 6px;
            page-break-after: avoid;
        }}

        /* Sub-seções do tópico: #### 1. Abertura, #### 2. Fundamentação… */
        h4 {{
            font-size: 12pt;
            color: #1a4a8a;
            font-weight: bold;
            border-left: 3px solid #5b8dd9;
            padding-left: 8px;
            margin-top: 18px;
            margin-bottom: 4px;
            page-break-after: avoid;
        }}

        h5 {{
            font-size: 11pt;
            color: #333;
            font-weight: bold;
            font-style: italic;
            margin-top: 14px;
            margin-bottom: 4px;
            page-break-after: avoid;
        }}

        h6 {{
            font-size: 10.5pt;
            color: #555;
            font-weight: bold;
            margin-top: 10px;
            margin-bottom: 2px;
        }}

        /* =====================================================================
           PARÁGRAFOS E TEXTO
        ===================================================================== */

        p {{
            margin: 7px 0 7px 0;
            text-align: justify;
            orphans: 3;
            widows: 3;
        }}

        strong {{
            color: #0d2f5e;
        }}

        em {{
            color: #333;
        }}

        /* =====================================================================
           LISTAS
        ===================================================================== */

        ul, ol {{
            margin: 8px 0 8px 28px;
            padding: 0;
        }}

        li {{
            margin-bottom: 5px;
            line-height: 1.55;
        }}

        li > ul, li > ol {{
            margin-top: 4px;
        }}

        /* =====================================================================
           TABELAS
        ===================================================================== */

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 14px 0;
            font-size: 10.5pt;
            page-break-inside: avoid;
        }}

        th {{
            background-color: #0d2f5e;
            color: #ffffff;
            padding: 8px 10px;
            text-align: left;
            font-size: 10pt;
            font-weight: bold;
        }}

        td {{
            padding: 6px 10px;
            border: 1px solid #c5d4e8;
            vertical-align: top;
        }}

        tr:nth-child(even) td {{
            background-color: #f2f6fb;
        }}

        tr:nth-child(odd) td {{
            background-color: #ffffff;
        }}

        /* =====================================================================
           CÓDIGO / BLOCOS PRÉ-FORMATADOS
        ===================================================================== */

        code {{
            background-color: #f4f4f4;
            border: 1px solid #ddd;
            border-radius: 3px;
            padding: 1px 5px;
            font-family: "Courier New", monospace;
            font-size: 10pt;
        }}

        pre {{
            background-color: #f4f4f4;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px 14px;
            overflow-x: auto;
            font-size: 9.5pt;
            page-break-inside: avoid;
        }}

        /* =====================================================================
           BLOCKQUOTE — caixas de atenção e destaques
        ===================================================================== */

        blockquote {{
            background-color: #fffbea;
            border-left: 5px solid #f0a800;
            margin: 12px 0;
            padding: 10px 14px;
            border-radius: 0 4px 4px 0;
            page-break-inside: avoid;
        }}

        blockquote p {{
            margin: 4px 0;
        }}

        hr {{
            border: none;
            border-top: 1px solid #c5d4e8;
            margin: 18px 0;
        }}

        /* =====================================================================
           QUESTÕES — evitar corte no meio da página
        ===================================================================== */

        .questao-objetiva,
        .questao-dissertativa,
        .questao-caso {{
            page-break-inside: avoid;
            margin: 10px 0 4px 0;
            font-weight: bold;
        }}

        .questao-num {{
            color: #1a4a8a;
            font-weight: bold;
        }}

        .alternativa {{
            margin: 2px 0 2px 22px;
            font-size: 11pt;
        }}

        .secao-questoes {{
            background-color: #f8fbff;
            border: 1px solid #c5d4e8;
            border-radius: 4px;
            padding: 12px 16px;
            margin: 16px 0;
        }}

        /* =====================================================================
           GABARITOS E CRITÉRIOS
        ===================================================================== */

        .gabarito {{
            background-color: #eaf4ea;
            border-left: 4px solid #27a025;
            padding: 8px 12px;
            margin: 6px 0;
            page-break-inside: avoid;
            border-radius: 0 4px 4px 0;
        }}

        .criterios {{
            background-color: #fff3e0;
            border-left: 4px solid #e67e00;
            padding: 8px 12px;
            margin: 6px 0;
            page-break-inside: avoid;
            border-radius: 0 4px 4px 0;
        }}

        /* =====================================================================
           CASOS PRÁTICOS — campos semânticos
        ===================================================================== */

        strong.campo-caso {{
            display: block;
            color: #0d2f5e;
            font-size: 10.5pt;
            margin-top: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* =====================================================================
           CONTROLE EDITORIAL
        ===================================================================== */

        .controle-editorial {{
            background-color: #f0f0f0;
            border: 1px dashed #aaa;
            border-radius: 4px;
            padding: 10px 14px;
            margin: 18px 0;
            font-size: 9.5pt;
            color: #555;
            page-break-inside: avoid;
        }}

        .controle-editorial strong {{
            color: #444;
        }}

        .controle-editorial table {{
            font-size: 9pt;
            margin: 6px 0 0 0;
        }}

        .controle-editorial th {{
            background-color: #888;
            font-size: 9pt;
        }}

        /* =====================================================================
           CAPA
        ===================================================================== */

        .capa {{
            text-align: center;
            padding-top: 160px;
            page-break-after: always;
        }}

        .capa h1 {{
            font-size: 26pt;
            color: #0d2f5e;
            border: none;
            margin-bottom: 10px;
        }}

        .capa h2 {{
            font-size: 18pt;
            color: #1a4a8a;
            border: none;
            margin-top: 8px;
        }}

        .capa .subtitulo {{
            font-size: 13pt;
            color: #555;
            margin-top: 20px;
        }}

        /* =====================================================================
           QUEBRAS DE PÁGINA
        ===================================================================== */

        .page-break {{
            page-break-after: always;
        }}

        .nova-disciplina {{
            page-break-before: always;
        }}

    </style>
</head>
<body>

    <!-- CAPA -->
    <div class="capa">
        <img src="data:image/jpeg;base64,{logo_base64}" width="130"><br><br>
        <h1>ESCOLA TÉCNICA SAN MARINO</h1>
        <h2>{nome_disciplina_display}</h2>
        <p class="subtitulo">{subtitulo_display}</p>
    </div>

    <!-- CONTEÚDO -->
    {conteudos_html}

</body>
</html>"""


# ---------------------------------------------------------------------------
# CONVERSÃO MARKDOWN → HTML COM PÓS-PROCESSAMENTO
# ---------------------------------------------------------------------------

def _md_para_html(md_texto: str) -> str:
    """Converte markdown para HTML com extensões e pós-processamento."""
    html = markdown.markdown(md_texto, extensions=MD_EXTENSIONS)
    html = _pos_processar_html(html)
    return html


# ---------------------------------------------------------------------------
# GERAÇÃO DE UM PDF A PARTIR DE UM ÚNICO .md
# ---------------------------------------------------------------------------

def _gerar_pdf_disciplina(md_path, pdf_path, nome_curso_display, disciplina, caderno, logo_base64):
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            md_texto = f.read()
    except Exception as e:
        print(f"   ⚠️  Erro ao ler {md_path}: {e}")
        return

    html_disciplina = _md_para_html(md_texto)
    subtitulo = "Caderno do Professor" if caderno == "professor" else "Caderno do Aluno"
    html_final = gerar_html_completo(
        conteudos_html=html_disciplina,
        nome_curso=nome_curso_display,
        logo_base64=logo_base64,
        nome_disciplina=disciplina.replace("_", " "),
        subtitulo_capa=subtitulo,
    )

    try:
        pdf_path = os.path.abspath(pdf_path)
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        pdfkit.from_string(
            html_final,
            tmp_path,
            configuration=_get_pdfkit_config(),
            options=WKHTMLTOPDF_OPTIONS,
        )
        shutil.move(tmp_path, pdf_path)
        print(f"   ✅ {caderno}/{disciplina}.pdf")
    except Exception as exc:
        print(f"   ❌ Erro ao gerar PDF ({disciplina}): {exc}")


# ---------------------------------------------------------------------------
# GERAÇÃO DAS APOSTILAS — 1 PDF por disciplina
# ---------------------------------------------------------------------------

def gerar_apostilas_por_disciplina(
    pasta_markdown="data/output/markdown",
    pasta_pdf="data/output/workbooks_pdf",
    logo_path="assets/logo.jpeg",
):
    """Gera um PDF por .md: workbooks_pdf/{aluno|professor}/{curso}/{disciplina}.pdf"""
    try:
        with open(logo_path, "rb") as img:
            logo_base64 = base64.b64encode(img.read()).decode()
    except FileNotFoundError:
        print(f"⚠️  Logo não encontrado em '{logo_path}'. Capa sem imagem.")
        logo_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    total = 0
    for curso in sorted(os.listdir(pasta_markdown)):
        caminho_curso = os.path.join(pasta_markdown, curso)
        if not os.path.isdir(caminho_curso):
            continue

        titulo_txt = os.path.join(caminho_curso, "_titulo.txt")
        if os.path.exists(titulo_txt):
            with open(titulo_txt, "r", encoding="utf-8") as _f:
                nome_curso_display = _f.read().strip() or curso
        else:
            nome_curso_display = curso

        print(f"\n📚 Curso: {nome_curso_display}")

        mds = sorted(f for f in os.listdir(caminho_curso) if f.endswith(".md") and not f.startswith("_"))

        for md_file in mds:
            eh_professor = md_file.endswith("_Professor.md")
            caderno = "professor" if eh_professor else "aluno"
            disciplina = md_file[:-len("_Professor.md")] if eh_professor else md_file[:-3]

            pdf_path = os.path.join(pasta_pdf, caderno, curso, f"{disciplina}.pdf")
            _gerar_pdf_disciplina(
                md_path=os.path.join(caminho_curso, md_file),
                pdf_path=pdf_path,
                nome_curso_display=nome_curso_display,
                disciplina=disciplina,
                caderno=caderno,
                logo_base64=logo_base64,
            )
            total += 1

    print(f"\n✅ Total de PDFs gerados: {total}")


# wrapper para compatibilidade com chamadas existentes em main.py
def gerar_apostilas_por_curso(
    pasta_markdown="data/output/markdown",
    pasta_pdf="data/output/workbooks_pdf",
    logo_path="assets/logo.jpeg",
):
    gerar_apostilas_por_disciplina(pasta_markdown, pasta_pdf, logo_path)
