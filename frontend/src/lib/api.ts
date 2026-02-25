import { AnalyzeResponse, FileEntry, Mode, MonoPolyOverride, SessionSummary } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";
const API_HOST = API_BASE.replace("/api/v1", "");

export interface AnalyzeRequest {
  file: File;
  mode: Mode;
  autoPitchTime: boolean;
  rootNote: string;
  scale: string;
  customScaleNotes: string[];
  bpm?: number;
  timeSignature?: string;
  monoPolyOverride: MonoPolyOverride;
  sessionId?: string;
}

async function safeJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Request failed." }));
    throw new Error(body.detail ?? "Request failed.");
  }
  return (await res.json()) as T;
}

function networkErrorMessage(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "Request timed out while waiting for backend response. Please try again.";
  }
  if (error instanceof Error && error.message) return error.message;
  return "Backend is not reachable. Ensure VINS backend is running on 127.0.0.1:8000.";
}

async function fetchWithTimeout(input: RequestInfo | URL, init?: RequestInit, timeoutMs = 12000): Promise<Response> {
  const controller = new AbortController();
  let didTimeout = false;
  const timer = setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);
  try {
    return await fetch(input, { ...(init ?? {}), signal: controller.signal });
  } catch (error) {
    if (didTimeout) {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s. Backend may still be processing.`);
    }
    const msg = networkErrorMessage(error);
    throw new Error(msg);
  } finally {
    clearTimeout(timer);
  }
}

export async function ensureBackendReady(retries = 20, intervalMs = 350): Promise<void> {
  let lastError = "Backend did not respond in time.";
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      const response = await fetchWithTimeout(`${API_BASE}/health`, { method: "GET" }, 2500);
      if (response.ok) return;
      lastError = `Backend health check failed with status ${response.status}.`;
    } catch (error) {
      lastError = networkErrorMessage(error);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(lastError);
}

export async function analyzeAudio(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("mode", payload.mode);
  form.append("auto_pitch_time", String(payload.autoPitchTime));
  form.append("root_note", payload.rootNote);
  form.append("scale", payload.scale);
  form.append("custom_scale_notes", payload.customScaleNotes.join(","));
  form.append("mono_poly_override", payload.monoPolyOverride);
  if (payload.bpm) form.append("bpm", String(payload.bpm));
  if (payload.timeSignature) form.append("time_signature", payload.timeSignature);
  if (payload.sessionId) form.append("session_id", payload.sessionId);
  const response = await fetchWithTimeout(`${API_BASE}/analyze`, { method: "POST", body: form }, 300000);
  return safeJson<AnalyzeResponse>(response);
}

export async function renameFile(
  sessionId: string,
  relativePath: string,
  newName: string
): Promise<FileEntry> {
  const response = await fetchWithTimeout(`${API_BASE}/files/${sessionId}/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: "any", relative_path: relativePath, new_name: newName })
  });
  return safeJson<FileEntry>(response);
}

export async function getSessions(): Promise<SessionSummary[]> {
  const response = await fetchWithTimeout(`${API_BASE}/sessions`, { method: "GET" }, 20000);
  return safeJson<SessionSummary[]>(response);
}

export async function getSessionFiles(sessionId: string): Promise<{ midi: FileEntry[]; audio: FileEntry[] }> {
  const response = await fetchWithTimeout(`${API_BASE}/sessions/${sessionId}/files`, { method: "GET" }, 20000);
  return safeJson<{ midi: FileEntry[]; audio: FileEntry[] }>(response);
}

export async function getDemoFiles(): Promise<Array<{ name: string; url: string }>> {
  const response = await fetchWithTimeout(`${API_BASE}/demo-files`, { method: "GET" }, 8000);
  const json = await safeJson<{ files: Array<{ name: string; url: string }> }>(response);
  return json.files;
}

export function fileUrl(relativeOrAbsolute: string): string {
  if (relativeOrAbsolute.startsWith("http")) return relativeOrAbsolute;
  if (relativeOrAbsolute.startsWith("/api")) {
    return `${API_HOST}${relativeOrAbsolute}`;
  }
  return `${API_BASE}/${relativeOrAbsolute.replace(/^\/+/, "")}`;
}

export function zipUrl(sessionId: string): string {
  return `${API_BASE}/sessions/${sessionId}/zip`;
}
