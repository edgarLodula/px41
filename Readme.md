# Gerador de Material Didático com IA

Sistema automatizado para produção de conteúdo educacional a partir de ementas em PDF, utilizando Inteligência Artificial para gerar apostilas, roteiros, áudios, slides e vídeos completos.

---

## Funcionalidades

- Extração automática de conteúdo de PDFs (com suporte a OCR)
- Geração de material didático com RAG + Google Gemini
- Criação de apostilas em PDF por curso
- Geração completa de videoaulas:
- Roteiro estruturado
- Áudio narrado (TTS)
- Slides ilustrativos
- Vídeo final com avatar

---

## Estrutura do Projeto

project/
├── data/
│ ├── input/ # PDFs de entrada (ementas)
│ └── output/
│ ├── json/ # Dados extraídos
│ ├── faiss/ # Índices vetoriais
│ ├── markdown/ # Conteúdo gerado por disciplina
│ ├── workbooks_pdf/ # Apostilas finais por curso
│ └── videos/ # Vídeos, áudios e slides por disciplina
├── assets/ # Logo, avatar e recursos estáticos
├── src/ # Módulos do sistema
├── main.py # Pipeline principal
├── requirements.txt
└── README.md


---

## 🚀 Instalação

### 1. Criar ambiente virtual

```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

## Configuração de APIs e Ferramentas

### Google Gemini

```bash
set GEMINI_API_KEY=sua_chave_aqui   # Windows
export GEMINI_API_KEY=sua_chave_aqui # Linux/Mac
```

### Groq

```bash
set GROQ_TOKEN=sua_chave_aqui
```

### Tesseract OCR

Baixe e instale em:

https://github.com/UB-Mannheim/tesseract/wiki

Configure no código:

```bash
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### PDFKit (wkhtmltopdf)

Baixe e instale:

https://wkhtmltopdf.org/downloads.html

Configure no código:

```bash
import pdfkit
config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
```

## Como Executar

```bash
python main.py
O pipeline executará automaticamente todas as etapas:
```

Extração do PDF → JSON estruturado

Indexação → Embeddings + FAISS

Geração de conteúdo → RAG + Gemini → Markdown

Criação de apostilas → Markdown → PDF

Produção de videoaulas → Roteiro → Áudio → Slides → Vídeo

## Saída Esperada

### Material em Markdown

```bash
data/output/markdown/curso_x/disciplina_1.md
data/output/markdown/curso_x/disciplina_2.md
```

### Apostilas em PDF

```bash
data/output/workbooks_pdf/curso_x.pdf
```

### Vídeos e recursos

```bash
data/output/videos/curso_x/disciplina_y/
├── audio.mp3
├── video.mp4
└── slides/
    ├── slide_001.png
    └── ...
```

## Tecnologias Utilizadas

Extração de PDF	- pytesseract, pdfplumber, Pillow
Indexação vetorial	- FAISS, sentence-transformers
Geração de texto	- Google Gemini API, Groq API
Formatação	- markdown, pdfkit, wkhtmltopdf
Produção de vídeo	- moviepy, gtts, pydub, Pillow, imageio-ffmpeg
Linguagem	- Python 3.11.9