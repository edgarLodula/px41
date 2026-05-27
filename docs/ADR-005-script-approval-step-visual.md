# ADR-005 — ScriptApprovalStep como etapa visual sem persistência

**Data:** 2026-05-13
**Status:** Aceito (com débito técnico documentado)

---

## Contexto

O fluxo de produto prevê 5 etapas no wizard do frontend:

1. Upload de PDFs
2. Processamento (polling do pipeline)
3. Aprovação da apostila
4. **Aprovação de roteiros** ← esta etapa
5. Acompanhamento e download dos vídeos

O problema identificado é uma **desincronização entre UX e backend**:

- Quando o usuário clica em "Aprovar" na etapa 3, o frontend chama `POST /approve`.
- O backend, ao receber `POST /approve`, **imediatamente inicia a geração dos vídeos** em background (`run_video()` em thread separada).
- O frontend então avança para a etapa 4 (ScriptApprovalStep), onde o usuário "revisa e aprova roteiros".
- Mas os vídeos **já estão sendo gerados** nesse momento — a aprovação dos roteiros na etapa 4 não tem efeito nenhum no backend.

Adicionalmente, os roteiros exibidos no `ScriptApprovalStep` são **textos mock hardcoded** (função `buildMockScript`), não os roteiros reais gerados pelo Gemini.

## Decisão

Manter a etapa visual por ora, adicionando um aviso explícito na UI:

> "⚠ Os vídeos já estão sendo gerados em background. Esta etapa é apenas de visualização."

Não remover o componente nem alterar o fluxo do wizard neste momento, pois a decisão de produto sobre o que fazer com essa etapa ainda não foi tomada.

## Débito técnico

Para que a etapa de aprovação de roteiros funcione de verdade, seriam necessárias as seguintes mudanças:

1. **Backend:** separar a geração de roteiros da geração de vídeos. O pipeline deveria parar em `awaiting_script_approval` após gerar os roteiros (via Gemini), expor os roteiros reais em um endpoint `GET /scripts`, e só gerar os vídeos após `POST /approve/script`.
2. **Frontend:** `ScriptApprovalStep` deveria buscar os roteiros reais via API em vez de usar o mock.
3. **Backend:** implementar `POST /approve/script` e `POST /reject/script`.

## Consequências

- UX atual: o usuário vê uma tela de "revisão" que não tem impacto real — pode gerar confusão.
- O aviso adicionado mitiga a confusão até que a decisão de produto seja tomada.
- A etapa 5 (VideoStep) funciona corretamente: faz polling até `status === "done"` e lista os vídeos via `GET /videos`.
