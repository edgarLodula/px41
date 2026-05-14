# ADR-002 — Limpeza e correção do requirements.txt

**Data:** 2026-05-13
**Status:** Aceito

---

## Contexto

O arquivo `requirements.txt` original apresentava três problemas que impediam a instalação limpa das dependências:

**1. Seção duplicada**
O arquivo continha duas listas concatenadas: a primeira com pacotes sem versão fixada (linhas 1–90) e a segunda com versões exatas (linhas 91–213). O pip tentava reconciliar ambas e entrava em conflito de resolução.

**2. Entrada corrompida**
A linha 91 continha `websocketsannotated-doc==0.0.4`, que era na verdade duas entradas fundidas de exportações diferentes (`websockets` e alguma variante de `annotated`). O pip não encontrava essa dependência e abortava toda a instalação.

**3. Conflito de versão: moviepy vs decorator**
A entrada `moviepy==1.0.3` exige `decorator<5.0`, mas `decorator==5.2.1` também estava especificado. Versões incompatíveis.

**4. Conflito de versão: moviepy vs pillow**
Após atualizar o moviepy para 2.2.1, surgiu conflito com `pillow==12.2.0` pois `moviepy==2.2.1` requer `pillow<12.0`.

## Decisão

1. Remover completamente a seção não versionada (linhas 1–90), mantendo apenas a seção com versões fixas.
2. Remover a linha corrompida `websocketsannotated-doc==0.0.4`.
3. Atualizar `moviepy==1.0.3` → `moviepy==2.2.1` (versão ativa, mantida).
4. Atualizar `pillow==12.2.0` → `pillow==11.2.1` (compatível com moviepy 2.2.1).
5. Remover `typer==0.24.2` — não utilizado em nenhum módulo do projeto e incompatível com `gTTS==2.5.4` (ambos disputam a versão do `click`).

## Consequências

- Instalação via `pip install -r requirements.txt` completa sem erros de resolução.
- O ambiente fica isolado na venv criada em `px41/venv/`.
- `moviepy 2.x` tem API ligeiramente diferente da 1.x em alguns métodos — se `audio_generator.py` ou `slides_generator.py` forem ativados no futuro, verificar compatibilidade.
- `pillow 11.x` é estável e compatível com todos os outros usos no projeto (PyMuPDF, pdfplumber, slides_generator).
