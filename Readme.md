# px41 — Gerador de Apostilas e Vídeos com IA

Sistema que transforma currículos escolares em apostilas PDF e vídeo-aulas com avatar, usando Gemini (Google AI) e HeyGen.

---

## Pré-requisitos

| Ferramenta | Versão | Download |
|---|---|---|
| Python | 3.11.x | [python.org](https://www.python.org/downloads/) |
| Git | qualquer | [git-scm.com](https://git-scm.com/) |
| wkhtmltopdf | 0.12.x | [wkhtmltopdf.org](https://wkhtmltopdf.org/downloads.html) — instalar em `C:\Program Files\wkhtmltopdf\` |

---

## Setup local (primeira vez)

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd px41
```

### 2. Crie e ative o ambiente virtual

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Se der erro de política de execução:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Copie o exemplo e preencha com suas chaves:

```bash
# Crie o arquivo .env na raiz do projeto
```

Conteúdo do `.env`:

```env
# Google Gemini — https://aistudio.google.com/app/apikey
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-2.5-flash

# HeyGen — https://app.heygen.com/home?nav=API
HEYGEN_API_KEY=sua_chave_aqui
HEYGEN_AVATAR_ID=id_do_avatar
HEYGEN_VOICE_ID=id_da_voz

# Opcional — background do vídeo (gerado pelo script abaixo)
HEYGEN_BG_ASSET_ID=
```

> **Atenção:** o `.env` está no `.gitignore` — nunca commite este arquivo.

### 5. (Opcional) Faça upload do background para o HeyGen

Execute uma única vez para registrar a imagem `assets/background_avatar.png`:

```bash
python scripts/upload_background_heygen.py
```

O `asset_id` será salvo automaticamente no `.env`.

### 6. Suba a API

```bash
uvicorn api:app --host 127.0.0.1 --port 8000
```

A API estará disponível em `http://localhost:8000`.  
Documentação interativa (Swagger): `http://localhost:8000/docs`

---

## Rodando os testes

```bash
# Verifica imports e configuração
python scripts/teste_recursos_api.py

# Testa os endpoints da API (requer API rodando)
python scripts/teste_endpoints_api.py

# Testa integração direta com o HeyGen
python scripts/teste_direto_heygen.py

# Diagnóstico da chave Gemini
python scripts/teste_gemini.py
```

---

## Estrutura do projeto

```
px41/
├── api.py                          # Servidor FastAPI — pipeline principal
├── requirements.txt                # Dependências Python
├── .env                            # Variáveis de ambiente (NÃO commitar)
│
├── src/
│   ├── syllabus_extractor/         # Extração de PDF → disciplinas (via Gemini)
│   ├── content_generation/         # RAG + Gemini → conteúdo didático
│   ├── output_formatter/           # Markdown por disciplina
│   ├── workbooks_generator/        # Markdown → PDF (apostila)
│   └── video_generator/
│       ├── gerador_videos_direto.py  # Pipeline de vídeo com aprovação por etapa
│       └── pipeline_video.py         # Pipeline legado (v2)
│
├── data/
│   ├── input/                      # PDFs de currículo enviados pelo usuário
│   └── output/
│       ├── json/                   # base_geral.json — disciplinas extraídas
│       ├── faiss/                  # Índice vetorial
│       ├── markdown/               # Conteúdo gerado por disciplina
│       ├── workbooks_pdf/          # Apostilas em PDF
│       ├── videos/                 # Vídeos do pipeline principal
│       └── jobs/                   # Jobs do gerador direto (artefatos por job_id)
│
├── assets/
│   └── background_avatar.png       # Fundo padrão dos vídeos
│
├── scripts/                        # Scripts de diagnóstico e teste
└── docs/                           # ADRs e documentação técnica
```

---

## Variáveis de ambiente — referência completa

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | Sim | Chave da API Google Gemini |
| `GEMINI_MODEL` | Não | Modelo Gemini (padrão: `gemini-2.5-flash`) |
| `HEYGEN_API_KEY` | Sim | Chave da API HeyGen (requer saldo de API credits) |
| `HEYGEN_AVATAR_ID` | Sim | ID do avatar a usar nos vídeos |
| `HEYGEN_VOICE_ID` | Sim | ID da voz do avatar |
| `HEYGEN_BG_ASSET_ID` | Não | Asset ID do background (gerado por `upload_background_heygen.py`) |

---

## Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/upload` | Envia PDFs e inicia o pipeline |
| `GET` | `/status` | Estado atual do pipeline |
| `GET` | `/disciplines` | Lista disciplinas encontradas (após extração) |
| `POST` | `/select-disciplines` | Seleciona quais disciplinas processar |
| `POST` | `/approve` | Aprova apostila e inicia geração de roteiros |
| `GET` | `/scripts` | Roteiros gerados para revisão |
| `POST` | `/approve/scripts` | Aprova roteiros (com edições opcionais) |
| `POST` | `/approve/scenes` | Aprova cenas e dispara HeyGen |
| `GET` | `/videos` | Lista vídeos prontos |
| `GET` | `/download/video/{nome}` | Download de vídeo por disciplina |
| `POST` | `/gerador-videos/iniciar` | Fluxo direto de vídeo (independente) |

Documentação completa: `http://localhost:8000/docs`

---

## Problemas comuns

**`GEMINI_API_KEY` retorna 403**
→ Verifique se a chave é válida e se o projeto Google Cloud tem billing ativo.

**HeyGen retorna `MOVIO_PAYMENT_INSUFFICIENT_CREDIT`**
→ A conta HeyGen precisa de **API credits** (saldo separado do plano web). Adicionar em: Settings → API → Billing.

**wkhtmltopdf não encontrado**
→ Instale em `C:\Program Files\wkhtmltopdf\` ou ajuste o caminho em `src/workbooks_generator/workbooks_generator.py`.

**Erro de política de execução no PowerShell**
→ Execute: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
