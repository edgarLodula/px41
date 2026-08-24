export const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ─── Upload ───────────────────────────────────────────────────────────────────
export async function uploadPDFs(files: File[], instructions?: string): Promise<void> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  if (instructions) form.append("instructions", instructions);

  const res = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload falhou: ${res.status} — ${text}`);
  }
}

// ─── Status ───────────────────────────────────────────────────────────────────
export interface StageInfo {
  name: string;
  status: "waiting" | "running" | "done" | "error";
}

export interface StatusResponse {
  status: "idle" | "running" | "awaiting_approval" | "done" | "error";
  stage: number;
  stages: StageInfo[];
  error: string | null;
}

export async function getStatus(): Promise<StatusResponse> {
  const res = await fetch(`${BASE_URL}/status`);
  if (!res.ok) throw new Error(`Status falhou: ${res.status}`);
  return res.json();
}

// ─── Helper interno: dispara download de um Blob com nome correto ─────────────
/**
 * Cria um <a> temporário, aciona o clique e só revoga a URL após um delay
 * para garantir que o browser já iniciou o download antes de liberar o blob.
 */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  // Aguarda 250 ms antes de revogar — tempo suficiente para o browser
  // enfileirar o download sem que a URL já tenha sido liberada.
  setTimeout(() => URL.revokeObjectURL(url), 250);
}

// ─── Download apostilas (ZIP com workbooks_pdf/aluno) ────────────────────────
export async function downloadApostila(): Promise<void> {
  const res = await fetch(`${BASE_URL}/download/apostilas-zip`);
  if (!res.ok) throw new Error(`Download das apostilas falhou: ${res.status}`);
  const blob = await res.blob();
  triggerBlobDownload(blob, "apostilas_aluno.zip");
}

// ─── Aprovar conteúdo ─────────────────────────────────────────────────────────
export async function approve(): Promise<void> {
  const res = await fetch(`${BASE_URL}/approve`, { method: "POST" });
  if (!res.ok) throw new Error(`Aprovação falhou: ${res.status}`);
}

// ─── Rejeitar conteúdo ────────────────────────────────────────────────────────
export async function reject(): Promise<void> {
  const res = await fetch(`${BASE_URL}/reject`, { method: "POST" });
  if (!res.ok) throw new Error(`Rejeição falhou: ${res.status}`);
}

// ─── Aprovar script ───────────────────────────────────────────────────────────
export async function approveScript(): Promise<void> {
  const res = await fetch(`${BASE_URL}/approve/scripts`, { method: "POST" });
  if (!res.ok) throw new Error(`Aprovação do script falhou: ${res.status}`);
}

// ─── Listar vídeos ────────────────────────────────────────────────────────────
export interface VideosListResponse {
  videos: string[];
}

/**
 * Busca a lista de vídeos disponíveis.
 * Endpoint separado de /download/videos para não conflitar com o download direto.
 */
export async function listVideos(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/videos`);
  if (!res.ok) throw new Error(`Listagem de vídeos falhou: ${res.status}`);
  const data: VideosListResponse = await res.json();
  return data.videos ?? [];
}

// ─── Download vídeo por nome ──────────────────────────────────────────────────
export async function downloadVideoByName(nome: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/download/video/${encodeURIComponent(nome)}`);
  if (!res.ok) throw new Error(`Download do vídeo "${nome}" falhou: ${res.status}`);

  // Tenta pegar o nome real sugerido pelo servidor
  const disposition = res.headers.get("content-disposition");
  const match = disposition?.match(/filename\*?=["']?(?:UTF-8'')?([^"';\r\n]+)/i);
  const filename = match?.[1] ? decodeURIComponent(match[1]) : `${nome}.mp4`;

  const blob = await res.blob();
  triggerBlobDownload(blob, filename);
}
