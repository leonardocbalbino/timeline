// Cliente da API do Íntegra (/api/v1). Autenticação por token Bearer guardado no SecureStore.
import Constants from 'expo-constants';
import { File, FileMode } from 'expo-file-system';
import { fetch } from 'expo/fetch';

export const API_URL: string =
  process.env.EXPO_PUBLIC_API_URL ?? (Constants.expoConfig?.extra?.apiUrl as string | undefined) ?? 'https://processointegra.com.br';

export type Plan = 'free' | 'pro';
export type Me = {
  user: { id: number; email: string; name: string };
  account: { id: number; name: string; plan: Plan; plan_label: string; pro_until: string | null };
  features: Record<'timeline_horizontal' | 'relatorio' | 'exportar' | 'verificar' | 'compartilhar' | 'auditoria', boolean>;
  limits: { processes: number; storage_mb: number };
  usage: { processes: number; storage_bytes: number };
};
export type ProcessSummary = {
  id: number; title: string; number: string; description: string; updated_at: string; shared: boolean;
  evidence_count?: number; first_at?: string | null; last_at?: string | null;
};
export type EvidenceFile = {
  id: number; name: string; kind: 'imagem' | 'audio' | 'video' | 'documento'; mime: string; size: number;
  sha256: string; uploaded_at: string; url: string;
};
export type Evidence = {
  id: number; occurred_at: string; title: string; description: string; source: string; people: string;
  important: boolean; files: EvidenceFile[];
};
export type VerifyResult = {
  name: string; sha256: string;
  matches: { id: number; original_name: string; uploaded_at: string; evidence_id: number; title: string;
    occurred_at: string; process_id: number; process_title: string }[];
};

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setToken(value: string | null) {
  token = value;
}
export function getToken() {
  return token;
}
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}
export function authHeaders(): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}
export function absoluteUrl(path: string) {
  return path.startsWith('http') ? path : API_URL + path;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = (await fetch(API_URL + path, {
      method,
      headers: { Accept: 'application/json', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...authHeaders() },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })) as unknown as Response;
  } catch {
    throw new ApiError('Sem conexão com o Íntegra. Verifique a internet e tente de novo.', 0);
  }
  let data: any = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  if (!res.ok) {
    if (res.status === 401 && token && path !== '/api/v1/login') onUnauthorized?.();
    throw new ApiError(data.error || `Erro ${res.status}`, res.status, data.code);
  }
  return data as T;
}

export const api = {
  login: (email: string, senha: string, device: string) =>
    request<Me & { token: string }>('POST', '/api/v1/login', { email, senha, device }),
  logout: () => request<{ ok: true }>('DELETE', '/api/v1/sessao'),
  me: () => request<Me>('GET', '/api/v1/me'),
  deleteAccount: (senha: string) => request<{ ok: true }>('POST', '/api/v1/conta/excluir', { senha }),
  processes: () => request<{ processes: ProcessSummary[] }>('GET', '/api/v1/processos'),
  createProcess: (titulo: string, numero: string, descricao: string) =>
    request<{ process: ProcessSummary }>('POST', '/api/v1/processos', { titulo, numero, descricao }),
  process: (id: number) => request<{ process: ProcessSummary; evidences: Evidence[] }>('GET', `/api/v1/processos/${id}`),
  shareLink: (id: number, novo = false) => request<{ url: string }>('POST', `/api/v1/processos/${id}/link`, { novo }),
  createEvidence: (pid: number, payload: {
    data: string; hora: string; titulo: string; descricao: string; origem: string; pessoas: string;
    destaque: boolean; upload_ids: string[];
  }) => request<{ evidence: Evidence }>('POST', `/api/v1/processos/${pid}/provas`, payload),
  updateEvidence: (pid: number, eid: number, payload: Partial<{ data: string; hora: string; titulo: string;
    descricao: string; origem: string; pessoas: string; destaque: boolean }>) =>
    request<{ evidence: Evidence }>('PATCH', `/api/v1/processos/${pid}/provas/${eid}`, payload),
  deleteEvidence: (pid: number, eid: number) => request<{ ok: true }>('DELETE', `/api/v1/processos/${pid}/provas/${eid}`),
  verify: (uploadId: string) => request<VerifyResult>('POST', '/api/v1/verificar', { upload_id: uploadId }),
};

// ------------------------------------------------------------ upload em partes
// O servidor está atrás do Cloudflare (limite de 100 MB por requisição): cada arquivo vai em pedaços,
// lidos do disco com FileHandle e enviados como bytes. Se a conexão cair, retoma de onde parou.
export type LocalFile = { uri: string; name: string; size: number; mimeType: string };

const CHUNK = 8 * 1024 * 1024;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function uploadInParts(
  file: LocalFile,
  purpose: 'prova' | 'verificar',
  onProgress: (sentBytes: number) => void,
): Promise<string> {
  const start = await request<{ id: string; chunk_size: number }>('POST', '/uploads/iniciar', {
    name: file.name, size: file.size, mime: file.mimeType, purpose,
  });
  const source = new File(file.uri);
  const handle = source.open(FileMode.ReadOnly);
  let offset = 0;
  let failures = 0;
  try {
    while (offset < file.size) {
      handle.offset = offset;
      const bytes = await handle.readBytes(Math.min(CHUNK, file.size - offset));
      if (!bytes.length) throw new ApiError(`Não foi possível ler “${file.name}”.`, 0);
      let res: Response | null = null;
      try {
        res = (await fetch(`${API_URL}/uploads/${start.id}/parte?offset=${offset}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/octet-stream', ...authHeaders() },
          body: bytes,
        })) as unknown as Response;
      } catch {
        res = null;
      }
      const data: any = res ? await res.json().catch(() => ({})) : {};
      if (res && (res.status === 200 || res.status === 409) && typeof data.received === 'number') {
        failures = data.received > offset ? 0 : failures + 1;
        offset = data.received;
        onProgress(offset);
      } else if (!res || res.status >= 500 || res.status === 408 || res.status === 429) {
        failures += 1;
        await sleep(1000 * 2 ** Math.min(failures, 5));
      } else {
        throw new ApiError(data.error || `Erro ${res.status} ao enviar “${file.name}”.`, res.status);
      }
      if (failures > 6) throw new ApiError(`Falha de conexão ao enviar “${file.name}”. Tente novamente.`, 0);
    }
  } finally {
    handle.close();
  }
  return start.id;
}
