# ADR-003 — Renomeação do endpoint de listagem de vídeos

**Data:** 2026-05-13
**Status:** Aceito

---

## Contexto

O backend expunha dois endpoints relacionados a vídeos:

- `GET /download/videos` — retornava JSON `{ "videos": ["disciplina1", ...] }` (apenas listagem)
- `GET /download/video/{nome}` — fazia download real do arquivo `.mp4`

O prefixo `/download/` no endpoint de listagem criou ambiguidade: o desenvolvedor do frontend interpretou que `GET /download/videos` faria um download direto de arquivo (por analogia com `GET /download/apostila`), e por isso criou um endpoint alternativo `GET /videos` no cliente, esperando que o backend o implementasse. O backend nunca implementou `GET /videos`, resultando em 404 em produção.

O comentário no frontend (`src/lib/api.ts`) registrava essa intenção equivocada:

```ts
/**
 * Busca a lista de vídeos disponíveis.
 * Endpoint separado de /download/videos para não conflitar com o download direto.
 */
```

## Decisão

Renomear o endpoint de listagem no backend de `GET /download/videos` para `GET /videos`, tornando a semântica explícita:

| Endpoint | Semântica |
|---|---|
| `GET /videos` | Lista nomes das disciplinas com vídeo disponível |
| `GET /download/video/{nome}` | Faz download do `.mp4` de uma disciplina |

Atualizar o frontend (`src/lib/api.ts`) para usar `GET /videos`.

## Consequências

- A nomenclatura agora segue o princípio de que o prefixo `/download/` só aparece em rotas que retornam arquivo binário.
- O endpoint `GET /download/video` (sem parâmetro, mantido por compatibilidade com frontend antigo) não foi alterado.
- O script `scripts/teste_endpoints_api.py` foi atualizado para refletir a nova URL.
- Qualquer cliente externo que chamava `GET /download/videos` precisa ser atualizado para `GET /videos`.
