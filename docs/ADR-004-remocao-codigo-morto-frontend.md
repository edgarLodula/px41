# ADR-004 — Remoção de código morto no frontend (approveScript / rejectScript)

**Data:** 2026-05-13
**Status:** Aceito

---

## Contexto

O arquivo `san-marino-booklet-creator/src/lib/api.ts` continha duas funções exportadas sem uso:

```ts
export async function approveScript(): Promise<void> {
  const res = await fetch(`${BASE_URL}/approve/script`, { method: "POST" });
  ...
}

export async function rejectScript(): Promise<void> {
  const res = await fetch(`${BASE_URL}/reject/script`, { method: "POST" });
  ...
}
```

Nenhum componente do frontend importava ou chamava essas funções. Os endpoints correspondentes (`POST /approve/script` e `POST /reject/script`) **nunca foram implementados no backend**.

A origem provável é uma versão anterior do fluxo de produto onde a aprovação de roteiros seria uma etapa com persistência no servidor. Essa ideia foi abandonada e o `ScriptApprovalStep` passou a ser uma etapa puramente visual (ver ADR-005), mas as funções de API não foram removidas.

## Decisão

Remover `approveScript` e `rejectScript` de `api.ts`.

## Consequências

- Redução de surface de API falsa — nenhum consumidor pode mais chamar endpoints que não existem.
- Se no futuro a aprovação de roteiros precisar ser persistida no servidor, as funções devem ser recriadas com endpoints correspondentes implementados no backend.
