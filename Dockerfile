FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependências de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-por \
    libsm6 \
    libxext6 \
    libgl1 \
    wget \
    curl \
    ca-certificates \
    xfonts-75dpi \
    xfonts-base \
    libxrender1 \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# wkhtmltopdf com suporte a Qt (versão headless para geração de PDF)
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    -O /tmp/wkhtmltox.deb \
    && dpkg -i /tmp/wkhtmltox.deb || apt-get install -f -y \
    && rm /tmp/wkhtmltox.deb

WORKDIR /app

COPY requirements.txt .

# Instala dependências Python
# Nota: torch==2.11.0 instalado via PyPI padrão.
# Para reduzir tamanho da imagem em deploy CPU-only, substituir por:
#   torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu
# (verificar compatibilidade antes de aplicar em produção)
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
