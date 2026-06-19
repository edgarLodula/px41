"""
Gerador de PDFs a partir dos Markdowns produzidos por gerar_markdowns.

Produz:
  workbooks_pdf/aluno/<curso>/<disciplina>.pdf
  workbooks_pdf/professor/<curso>/<disciplina>.pdf

wkhtmltopdf é resolvido na ordem:
  1. Variável de ambiente WKHTMLTOPDF_PATH
  2. Executável no PATH do sistema
  3. Caminhos padrão por plataforma
"""
import os
import re
import sys
import shutil
import tempfile
import base64
import logging

import markdown

logger = logging.getLogger(__name__)

# Tenta importar pdfkit — opcional
try:
    import pdfkit
    _PDFKIT_DISPONIVEL = True
except ImportError:
    _PDFKIT_DISPONIVEL = False
    logger.warning("pdfkit não instalado. Geração de PDF não estará disponível.")


# ---------------------------------------------------------------------------
# LOCALIZAÇÃO DO WKHTMLTOPDF
# ---------------------------------------------------------------------------

_WKHTMLTOPDF_PATHS_PADRAO: list[str] = []
if sys.platform == "win32":
    _WKHTMLTOPDF_PATHS_PADRAO = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    ]
elif sys.platform == "darwin":
    _WKHTMLTOPDF_PATHS_PADRAO = [
        "/usr/local/bin/wkhtmltopdf",
        "/opt/homebrew/bin/wkhtmltopdf",
    ]
else:
    _WKHTMLTOPDF_PATHS_PADRAO = [
        "/usr/local/bin/wkhtmltopdf",
        "/usr/bin/wkhtmltopdf",
    ]


def _resolver_wkhtmltopdf() -> str | None:
    # 1. Variável de ambiente
    path_env = os.getenv("WKHTMLTOPDF_PATH", "").strip()
    if path_env and os.path.isfile(path_env):
        return path_env

    # 2. PATH do sistema
    path_sys = shutil.which("wkhtmltopdf")
    if path_sys:
        return path_sys

    # 3. Caminhos padrão
    for c in _WKHTMLTOPDF_PATHS_PADRAO:
        if os.path.isfile(c):
            return c

    return None


def _get_pdfkit_config():
    if not _PDFKIT_DISPONIVEL:
        raise RuntimeError(
            "pdfkit não está instalado. Execute: pip install pdfkit"
        )

    caminho = _resolver_wkhtmltopdf()
    if caminho:
        return pdfkit.configuration(wkhtmltopdf=caminho)
    try:
        return pdfkit.configuration()
    except OSError:
        raise OSError(
            "wkhtmltopdf não encontrado. Instale em https://wkhtmltopdf.org/downloads.html "
            "ou defina WKHTMLTOPDF_PATH no .env. "
            f"Caminhos tentados: {_WKHTMLTOPDF_PATHS_PADRAO}"
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

MD_EXTENSIONS = ["tables", "fenced_code", "nl2br", "sane_lists", "attr_list"]


# ---------------------------------------------------------------------------
# PÓS-PROCESSAMENTO HTML
# ---------------------------------------------------------------------------

def _pos_processar_html(html: str) -> str:
    html = re.sub(r"(<p>)(Q\d{1,2}\.\s)",
                  r'<p class="questao-objetiva"><span class="questao-num">\2</span>', html)
    html = re.sub(r"(<p>)([A-D]\))", r'<p class="alternativa">\2', html)
    html = re.sub(r"(<p>)(D\d\.\s)",
                  r'<p class="questao-dissertativa"><span class="questao-num">\2</span>', html)
    html = re.sub(r"(<p>)(CP\d\.\s)",
                  r'<p class="questao-caso"><span class="questao-num">\2</span>', html)
    html = re.sub(r"(<p>)(Gabarito\s*(?:das\s*\w+)?:?\s)",
                  r'<p class="gabarito"><strong>\2</strong>', html)
    html = re.sub(r"(<p>)(Crit[eé]rios?\s)",
                  r'<p class="criterios"><strong>\2</strong>', html)
    return html


# ---------------------------------------------------------------------------
# TEMPLATE HTML
# ---------------------------------------------------------------------------

def gerar_html_completo(
    conteudos_html: str,
    nome_curso: str,
    logo_base64: str,
    nome_disciplina: str | None = None,
    subtitulo_capa: str | None = None,
) -> str:
    nome_curso_display = nome_curso.replace("_", " ")
    nome_disciplina_display = (
        nome_disciplina.replace("_", " ") if nome_disciplina else nome_curso_display
    )
    subtitulo_display = subtitulo_capa or f"Material Didático — {nome_curso_display}"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <style>
        *{{box-sizing:border-box}}
        body{{font-family:"Arial",sans-serif;font-size:11.5pt;line-height:1.65;color:#1a1a1a;margin:0;padding:0}}
        h1.titulo-disciplina{{font-size:22pt;color:#0d2f5e;border-bottom:4px solid #0d2f5e;padding-bottom:8px;margin-top:0}}
        h2{{font-size:16pt;color:#1a4a8a;border-bottom:2px solid #1a4a8a;padding-bottom:4px;margin-top:28px;page-break-after:avoid}}
        h3{{font-size:13.5pt;color:#0d2f5e;background-color:#eef4fb;border-left:5px solid #1a4a8a;padding:6px 10px;margin-top:24px;page-break-after:avoid}}
        h4{{font-size:12pt;color:#1a4a8a;border-left:3px solid #5b8dd9;padding-left:8px;margin-top:18px;page-break-after:avoid}}
        p{{margin:7px 0;text-align:justify;orphans:3;widows:3}}
        strong{{color:#0d2f5e}}
        ul,ol{{margin:8px 0 8px 28px;padding:0}}
        li{{margin-bottom:5px}}
        table{{width:100%;border-collapse:collapse;margin:14px 0;font-size:10.5pt;page-break-inside:avoid}}
        th{{background-color:#0d2f5e;color:#fff;padding:8px 10px;text-align:left}}
        td{{padding:6px 10px;border:1px solid #c5d4e8;vertical-align:top}}
        tr:nth-child(even) td{{background-color:#f2f6fb}}
        code{{background-color:#f4f4f4;border:1px solid #ddd;border-radius:3px;padding:1px 5px;font-size:10pt}}
        pre{{background-color:#f4f4f4;border:1px solid #ddd;border-radius:4px;padding:10px 14px;page-break-inside:avoid}}
        blockquote{{background-color:#fffbea;border-left:5px solid #f0a800;margin:12px 0;padding:10px 14px;page-break-inside:avoid}}
        hr{{border:none;border-top:1px solid #c5d4e8;margin:18px 0}}
        .questao-objetiva,.questao-dissertativa,.questao-caso{{page-break-inside:avoid;margin:10px 0 4px;font-weight:bold}}
        .questao-num{{color:#1a4a8a;font-weight:bold}}
        .alternativa{{margin:2px 0 2px 22px;font-size:11pt}}
        .gabarito{{background-color:#eaf4ea;border-left:4px solid #27a025;padding:8px 12px;margin:6px 0;page-break-inside:avoid}}
        .criterios{{background-color:#fff3e0;border-left:4px solid #e67e00;padding:8px 12px;margin:6px 0;page-break-inside:avoid}}
        .capa{{text-align:center;padding-top:160px;page-break-after:always}}
        .capa h1{{font-size:26pt;color:#0d2f5e;border:none;margin-bottom:10px}}
        .capa h2{{font-size:18pt;color:#1a4a8a;border:none;margin-top:8px}}
        .capa .subtitulo{{font-size:13pt;color:#555;margin-top:20px}}
        .page-break{{page-break-after:always}}
    </style>
</head>
<body>
    <div class="capa">
        <img src="data:image/jpeg;base64,{logo_base64}" width="130"><br><br>
        <h1>ESCOLA TÉCNICA SAN MARINO</h1>
        <h2>{nome_disciplina_display}</h2>
        <p class="subtitulo">{subtitulo_display}</p>
    </div>
    {conteudos_html}
</body>
</html>"""


# ---------------------------------------------------------------------------
# CONVERSÃO MARKDOWN → HTML
# ---------------------------------------------------------------------------

def _md_para_html(md_texto: str) -> str:
    html = markdown.markdown(md_texto, extensions=MD_EXTENSIONS)
    return _pos_processar_html(html)


# ---------------------------------------------------------------------------
# VALIDAÇÃO DO PDF GERADO
# ---------------------------------------------------------------------------

def _validar_pdf(caminho: str) -> bool:
    """Verifica que o arquivo existe, tem tamanho > 0 e começa com '%PDF'."""
    if not os.path.isfile(caminho):
        return False
    if os.path.getsize(caminho) == 0:
        return False
    with open(caminho, "rb") as f:
        cabecalho = f.read(5)
    return cabecalho.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# GERAÇÃO DE UM PDF POR DISCIPLINA
# ---------------------------------------------------------------------------

def _gerar_pdf_disciplina(
    md_path: str,
    pdf_path: str,
    nome_curso_display: str,
    disciplina: str,
    caderno: str,
    logo_base64: str,
) -> bool:
    """Retorna True se o PDF foi gerado com sucesso."""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            md_texto = f.read()
    except Exception as exc:
        logger.error("Erro ao ler '%s': %s", md_path, exc)
        return False

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
        config = _get_pdfkit_config()
    except (RuntimeError, OSError) as exc:
        logger.error("wkhtmltopdf não disponível: %s", exc)
        print(f"   ⚠️  {exc}")
        return False

    pdf_path = os.path.abspath(pdf_path)
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    dir_destino = os.path.dirname(pdf_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_destino, suffix=".pdf")
    try:
        os.close(fd)
        pdfkit.from_string(
            html_final,
            tmp_path,
            configuration=config,
            options=WKHTMLTOPDF_OPTIONS,
        )
        shutil.move(tmp_path, pdf_path)
    except Exception as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        logger.error("Erro ao gerar PDF '%s': %s", pdf_path, exc)
        print(f"   ❌ Erro ao gerar PDF ({disciplina}): {exc}")
        return False

    if not _validar_pdf(pdf_path):
        logger.error("PDF gerado inválido: %s", pdf_path)
        return False

    print(f"   ✅ {caderno}/{disciplina}.pdf")
    return True


# ---------------------------------------------------------------------------
# PONTO DE ENTRADA PRINCIPAL
# ---------------------------------------------------------------------------

def gerar_apostilas_por_disciplina(
    pasta_markdown: str = "data/output/markdown",
    pasta_pdf: str = "data/output/workbooks_pdf",
    logo_path: str = "assets/logo.jpeg",
) -> int:
    """Gera PDFs para todos os .md encontrados. Retorna número de PDFs gerados."""
    if not _PDFKIT_DISPONIVEL:
        logger.error("pdfkit não instalado. Geração de PDF abortada.")
        print("❌ pdfkit não instalado. Use: pip install pdfkit")
        return 0

    try:
        with open(logo_path, "rb") as img:
            logo_base64 = base64.b64encode(img.read()).decode()
    except FileNotFoundError:
        logger.warning("Logo não encontrado em '%s'. Usando placeholder.", logo_path)
        # 1×1 pixel PNG transparente
        logo_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )

    total = 0

    if not os.path.isdir(pasta_markdown):
        logger.error("Diretório de Markdown não encontrado: %s", pasta_markdown)
        return 0

    for curso in sorted(os.listdir(pasta_markdown)):
        caminho_curso = os.path.join(pasta_markdown, curso)
        if not os.path.isdir(caminho_curso):
            continue

        titulo_txt = os.path.join(caminho_curso, "_titulo.txt")
        nome_curso_display = curso
        if os.path.isfile(titulo_txt):
            with open(titulo_txt, "r", encoding="utf-8") as _f:
                nome_curso_display = _f.read().strip() or curso

        print(f"\n📚 Curso: {nome_curso_display}")

        mds = sorted(
            f for f in os.listdir(caminho_curso)
            if f.endswith(".md") and not f.startswith("_")
        )

        for md_file in mds:
            eh_professor = md_file.endswith("_Professor.md")
            caderno = "professor" if eh_professor else "aluno"
            disciplina = (
                md_file[: -len("_Professor.md")] if eh_professor else md_file[:-3]
            )

            pdf_path = os.path.join(pasta_pdf, caderno, curso, f"{disciplina}.pdf")
            ok = _gerar_pdf_disciplina(
                md_path=os.path.join(caminho_curso, md_file),
                pdf_path=pdf_path,
                nome_curso_display=nome_curso_display,
                disciplina=disciplina,
                caderno=caderno,
                logo_base64=logo_base64,
            )
            if ok:
                total += 1

    print(f"\n✅ Total de PDFs gerados: {total}")
    return total


def gerar_apostilas_por_curso(
    pasta_markdown: str = "data/output/markdown",
    pasta_pdf: str = "data/output/workbooks_pdf",
    logo_path: str = "assets/logo.jpeg",
) -> int:
    """Alias de compatibilidade."""
    return gerar_apostilas_por_disciplina(pasta_markdown, pasta_pdf, logo_path)
