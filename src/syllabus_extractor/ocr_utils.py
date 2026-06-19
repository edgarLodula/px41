"""
Utilitários de OCR com Tesseract.

O caminho do binário é resolvido na seguinte ordem:
  1. Variável de ambiente TESSERACT_PATH
  2. Tesseract disponível no PATH do sistema
  3. Caminhos padrão por plataforma (fallback)
"""
import os
import shutil
import sys
import logging

import pytesseract
from PIL import Image
import io

logger = logging.getLogger(__name__)


def _resolver_tesseract() -> str | None:
    """Retorna o caminho do executável Tesseract ou None se não encontrado."""

    # 1. Variável de ambiente explícita
    path_env = os.getenv("TESSERACT_PATH", "").strip()
    if path_env and os.path.isfile(path_env):
        return path_env

    # 2. PATH do sistema
    path_sys = shutil.which("tesseract")
    if path_sys:
        return path_sys

    # 3. Caminhos padrão por plataforma
    candidatos: list[str] = []
    if sys.platform == "win32":
        candidatos = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
    elif sys.platform == "darwin":
        candidatos = [
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
        ]
    else:  # Linux
        candidatos = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]

    for c in candidatos:
        if os.path.isfile(c):
            return c

    return None


_TESSERACT_PATH = _resolver_tesseract()

if _TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH
    logger.debug("Tesseract localizado em: %s", _TESSERACT_PATH)
else:
    logger.warning(
        "Tesseract não encontrado. OCR não estará disponível. "
        "Instale Tesseract e defina TESSERACT_PATH no .env se necessário. "
        "Consulte: https://github.com/UB-Mannheim/tesseract/wiki (Windows) "
        "ou 'sudo apt install tesseract-ocr' (Linux)."
    )


def tesseract_disponivel() -> bool:
    return _TESSERACT_PATH is not None


def extrair_texto_com_ocr(page) -> str:
    """
    Extrai texto de uma página via OCR (Tesseract).
    `page` deve ser um objeto de página do PyMuPDF (fitz.Page).
    """
    if not tesseract_disponivel():
        raise RuntimeError(
            "Tesseract não está disponível. "
            "Instale o executável e defina TESSERACT_PATH no .env."
        )

    pix = page.get_pixmap(dpi=300)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang="por")
