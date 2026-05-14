# Decisões de Arquitetura (ADRs)

Registro das decisões técnicas tomadas no projeto, com contexto e justificativa.

| # | Título | Status | Data |
|---|--------|--------|------|
| [ADR-001](./ADR-001-lazy-loading-wkhtmltopdf.md) | Lazy loading da configuração do wkhtmltopdf | Aceito | 2026-05-13 |
| [ADR-002](./ADR-002-correcao-requirements.md) | Limpeza e correção do requirements.txt | Aceito | 2026-05-13 |
| [ADR-003](./ADR-003-renomeacao-endpoint-videos.md) | Renomeação do endpoint de listagem de vídeos | Aceito | 2026-05-13 |
| [ADR-004](./ADR-004-remocao-codigo-morto-frontend.md) | Remoção de código morto no frontend | Aceito | 2026-05-13 |
| [ADR-005](./ADR-005-script-approval-step-visual.md) | ScriptApprovalStep como etapa visual sem persistência | Aceito (débito técnico) | 2026-05-13 |

## O que é um ADR?

Um **Architecture Decision Record** documenta uma decisão técnica significativa: o contexto que levou a ela, o que foi decidido e quais as consequências. O objetivo é que qualquer pessoa que entre no projeto entenda **por que** o código está como está, não apenas **o que** ele faz.

## Como adicionar um novo ADR

1. Criar o arquivo `docs/ADR-NNN-titulo-curto.md` seguindo o template dos existentes.
2. Adicionar a linha correspondente na tabela acima.
3. Commitar junto com as mudanças de código que a decisão descreve.
