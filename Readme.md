# Gerador de Material Didático com IA

Projeto para **extração automática de ementas de cursos em PDF**, geração de **conteúdo didático com IA (RAG)** e criação de **apostilas completas em PDF organizadas por curso**.

---

## Visão Geral

O sistema realiza um pipeline completo:

1. Lê PDFs de cursos
2. Extrai disciplinas, ementas e conteúdos
3. Gera embeddings e indexa com FAISS
4. Usa IA (Gemini) para gerar material didático
5. Cria arquivos Markdown por disciplina
6. Consolida tudo em **apostilas por curso (PDF)**

---

## 📂 Estrutura do Projeto

```
project/
│
├── data/
│   ├── input/                 # PDFs de entrada
│   └── output/
│       ├── json/              # Base estruturada
│       ├── faiss/             # Índice vetorial
│       ├── markdown/          # Conteúdo gerado por disciplina
│       │   └── curso_x/
│       │       ├── disciplina_1.md
│       │       └── disciplina_2.md
│       └── workbooks_pdf/     # Apostilas finais
│
├── assets/
│   └── logo.jpeg              # Logo da instituição
│
├── src/
│   ├── syllabus_extractor/    # Extração de PDFs + OCR
│   ├── content_generation/    # RAG + IA (Gemini)
│   ├── output_formatter/      # Geração de Markdown
│   └── workbooks_generator/   # Geração de PDFs
│
├── main.py                    # Pipeline principal
├── requirements.txt
└── README.md
```

---

## Instalação

### 1. Criar ambiente virtual

```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

---

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

---

## Configuração da API (Gemini)

Crie um arquivo `.env` na raiz:

```
GEMINI_API_KEY=sua_chave_aqui
```

Ou no Windows:

```bash
set GEMINI_API_KEY=sua_chave_aqui
```

---

## OCR (Tesseract)

Necessário para PDFs escaneados.

### Instalar:

https://github.com/UB-Mannheim/tesseract/wiki

### Configurar no código:

```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

---

## Geração de PDF

O projeto usa:

* `pdfkit`
* `wkhtmltopdf`

### Instalar wkhtmltopdf:

https://wkhtmltopdf.org/downloads.html

### Caminho padrão:

```python
wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
```

---

## ▶️ Como Executar

### Pipeline completo:

```bash
python main.py
```

---

## Fluxo de Execução

### 1. Extração

```
PDF → JSON estruturado
```

### 2. Processamento semântico

```
JSON → embeddings → FAISS
```

### 3. Geração com IA

```
RAG + Gemini → Markdown por disciplina
```

### 4. Geração de apostilas

```
Markdown → PDF por curso
```

---

## Saída Esperada

### Markdown:

```
data/output/markdown/
    curso_x/
        disciplina_1.md
        disciplina_2.md
```

### Apostilas:

```
data/output/workbooks_pdf/
    curso_x.pdf
```

Cada PDF contém:

* Capa institucional
* Todas as disciplinas do curso
* Quebra de página entre conteúdos

---

## Observações

* O nome do curso é derivado automaticamente (ex: nome do arquivo PDF)
* O sistema pode sofrer rate limit da API do Gemini
* OCR só é usado quando necessário (fallback)

---

## Tecnologias Utilizadas

* Python
* FAISS (busca vetorial)
* Sentence Transformers
* Google Gemini API
* PyMuPDF / pdfplumber
* Tesseract OCR
* Markdown
* pdfkit / wkhtmltopdf