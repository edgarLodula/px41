# ADR-001 — Lazy loading da configuração do wkhtmltopdf

**Data:** 2026-05-13
**Status:** Aceito

---

## Contexto

O módulo `src/workbooks_generator/workbooks_generator.py` inicializava a configuração do `pdfkit` na linha 7, em escopo de módulo (fora de qualquer função):

```python
config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
```

O `pdfkit` tenta abrir o executável no momento da criação do objeto `Configuration`. Como o `wkhtmltopdf` não estava instalado no ambiente de desenvolvimento, essa linha lançava `OSError` **no momento do import** do módulo — antes mesmo de a API FastAPI terminar de inicializar — derrubando o servidor inteiro.

O erro observado:

```
OSError: No wkhtmltopdf executable found: "C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
```

## Decisão

Mover a criação do objeto `Configuration` para dentro da função `gerar_apostilas_por_curso`, que é o único lugar onde ele é utilizado. O caminho do executável foi extraído para uma constante no topo do módulo:

```python
WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'

def gerar_apostilas_por_curso(...):
    ...
    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
    pdfkit.from_string(html_final, caminho_pdf, configuration=config)
```

## Consequências

- A API sobe normalmente mesmo sem o `wkhtmltopdf` instalado.
- A falha ocorre apenas quando a etapa de geração de apostilas é acionada, com mensagem de erro clara e localizada.
- Para uso em produção, o `wkhtmltopdf` continua precisando ser instalado no servidor. Ver ADR-002 para discussão sobre alternativas.

## Notas

O `wkhtmltopdf` é um binário externo baseado em QtWebKit, abandonado desde 2020. Para deploy em cloud (Heroku, Railway, Render, etc.) sem Docker, a alternativa recomendada é o `WeasyPrint` (puro Python, instalável via pip). A migração deve ser feita após validação dos resultados visuais das apostilas geradas com a stack atual.
