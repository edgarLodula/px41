# ADR-006 — Gerador de Vídeos Direto com aprovação por etapa

**Data:** 2026-05-13
**Status:** Aceito

---

## Contexto

O pipeline principal estava bloqueado pela função `processar_pdf` incompleta. Para avançar de forma independente na integração HeyGen, foi criado um fluxo paralelo.

A versão inicial (v1) enviava o PDF direto ao HeyGen sem nenhuma revisão intermediária — qualquer erro ou conteúdo inadequado resultava em custo de crédito desperdiçado. Além disso, vídeos consomem créditos significativos, tornando obrigatória uma etapa de revisão humana antes de cada chamada externa custosa.

## Decisão

Redesenhar o fluxo como uma **máquina de estados com aprovação humana em cada etapa**:

```
PDF → [extração] → ✅ REVISÃO DO MARKDOWN
    → [Gemini]   → ✅ REVISÃO DO ROTEIRO
    → [Gemini]   → ✅ REVISÃO DO PLANO DE CENAS
    → [HeyGen]   → ✅ VÍDEO PRONTO
```

Em cada etapa de revisão, o usuário pode **editar livremente** o conteúdo gerado antes de avançar. O sistema só chama a API seguinte após aprovação explícita.

### Endpoints

| Método | Rota | Etapa |
|--------|------|-------|
| `POST` | `/gerador-videos/iniciar` | Upload do PDF → extração |
| `GET`  | `/gerador-videos/status/{job_id}` | Estado + conteúdo atual |
| `POST` | `/gerador-videos/aprovar-markdown/{job_id}` | Aprovação → gera roteiro |
| `POST` | `/gerador-videos/aprovar-roteiro/{job_id}` | Aprovação → gera cenas |
| `POST` | `/gerador-videos/aprovar-cenas/{job_id}` | Aprovação → gera vídeo |
| `GET`  | `/gerador-videos/heygen-status/{video_id}` | Status direto no HeyGen |

### Estados do job

```
extracting → awaiting_md_approval
  → generating_script → awaiting_script_approval
  → generating_scenes → awaiting_scenes_approval
  → generating_video  → completed | error
```

### Limites removíveis

Definidos como constantes em `gerador_videos_direto.py`:

```python
LIMITE_DISCIPLINAS  = 1    # disciplinas por PDF
LIMITE_PALAVRAS     = 80   # palavras no roteiro (~37s de vídeo)
LIMITE_PALAVRAS_MD  = 1200 # chars do markdown enviados ao Gemini
```

### HeyGen v3

Migrado de v2 para v3 (`POST /v3/videos`, `GET /v3/videos/{id}`).
Usa `Idempotency-Key` (UUID por request) para evitar cobranças duplicadas em retries.
Engine padrão: `avatar_iv`. Suporte a `avatar_v` disponível se o avatar for elegível.

## Consequências

- Cada chamada custosa (Gemini para roteiro, Gemini para cenas, HeyGen) só ocorre após aprovação explícita.
- O usuário pode corrigir o markdown (se a extração do PDF for imprecisa), ajustar o roteiro (tom, tamanho, informações) e revisar as cenas antes de gastar crédito no HeyGen.
- Polling de 3s no frontend mantém a UI atualizada durante as etapas de geração.

## Débito técnico

- **Estado em memória:** os jobs se perdem ao reiniciar o servidor. Persistir em Redis ou banco para produção.
- **Sem webhook HeyGen:** polling ativo durante a renderização. Implementar `callback_url` quando o servidor tiver URL pública.
- **Sem autenticação:** rotas `/gerador-videos/*` são públicas. Adicionar autenticação antes de deploy.
- **Uma disciplina por vez:** `LIMITE_DISCIPLINAS = 1` deve ser aumentado quando o fluxo estiver validado.


**Data:** 2026-05-13
**Status:** Aceito

---

## Contexto

O pipeline principal (upload de PDF → extração → conteúdo → apostila → vídeo) depende da função `processar_pdf` que está incompleta (ver análise da base de código). Isso bloqueia qualquer teste do módulo de vídeo HeyGen, que é a responsabilidade principal desta equipe.

Adicionalmente, a versão legacy do HeyGen (v2) usada no código original não é mais o padrão recomendado. A HeyGen lançou a v3 com:
- Endpoint unificado `POST /v3/videos`
- Status via `GET /v3/videos/{video_id}` (sem query string)
- `Idempotency-Key` para retries seguros
- Suporte a Avatar IV e V engines
- `callback_url` para webhooks em produção

A v2 permanece funcional até 31/10/2026, mas não recebe novos recursos.

## Decisão

Criar um **fluxo paralelo e independente** (`gerador_videos_direto.py`) que:

1. Recebe um PDF diretamente (sem depender do pipeline principal)
2. Extrai disciplinas via `pdfplumber` (mesmo approach do `csv_processor`)
3. Gera um roteiro curto de introdução via Gemini
4. Envia para o HeyGen usando a **API v3**
5. Aguarda e baixa o vídeo

### Limites removíveis (para testes controlados)

Definidos como constantes no topo de `gerador_videos_direto.py`:

```python
LIMITE_DISCIPLINAS  = 1   # processa apenas 1 disciplina por PDF
LIMITE_PALAVRAS     = 60  # roteiro de ~30 segundos (~130 wpm)
```

Esses limites evitam consumo acidental de créditos durante o desenvolvimento.

### Rotas adicionadas

| Método | Rota | Função |
|--------|------|--------|
| `POST` | `/gerador-videos/processar` | Recebe PDF e inicia job |
| `GET`  | `/gerador-videos/status/{job_id}` | Acompanha o job |
| `GET`  | `/gerador-videos/video/{job_id}/{disciplina}` | Download do vídeo |
| `GET`  | `/gerador-videos/heygen-status/{video_id}` | Status direto no HeyGen v3 |

### Frontend

Nova página em `/gerador-videos` com:
- Upload de PDF (drag & drop)
- Exibição do progresso por etapa
- Player de vídeo inline ao final
- Link de download

## Consequências

- A geração de vídeos pode ser testada independentemente do pipeline principal.
- O fluxo usa HeyGen v3, alinhado com o roadmap atual da plataforma.
- O `Idempotency-Key` (UUID por request) evita cobranças duplicadas em retries.
- Quando o pipeline principal for corrigido, o `gerador_videos_direto` pode ser descontinuado ou mantido como "modo rápido" para testes.

## Débito técnico

- **Sem webhook:** o polling atual funciona mas é ineficiente para produção. Implementar `callback_url` + endpoint `POST /heygen-webhook` quando o servidor tiver URL pública.
- **Estado em memória (`_jobs`):** os jobs se perdem ao reiniciar o servidor. Para produção, persistir em Redis ou banco.
- **Sem autenticação:** as rotas `/gerador-videos/*` são públicas. Adicionar autenticação antes de deploy.
