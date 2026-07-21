// ─── API client for llm-gateway backend ────────────────────────────────────
// Talks to /admin/keys* and /admin/monitor* on the FastAPI backend.
// Base URL and admin bearer token come from Vite env vars / localStorage.

export const API_BASE_URL: string =
  (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8000";

const TOKEN_STORAGE_KEY = "llm_gateway_admin_token";

export function getAdminToken(): string {
  return localStorage.getItem(TOKEN_STORAGE_KEY) ?? "";
}

export function setAdminToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearAdminToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

// ─── Types mirroring backend Pydantic schemas ──────────────────────────────
export type ApiKeyStatus = "active" | "cooldown" | "exhausted" | "disabled";
export type ApiProvider = "gemini";

export interface ApiKeyRead {
  id: number;
  label: string;
  provider: ApiProvider;
  status: ApiKeyStatus;
  requests_today: number;
  daily_limit: number;
  cooldown_until: string | null;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyCreate {
  label: string;
  provider: ApiProvider;
  raw_key: string;
  daily_limit: number;
}

export interface ApiKeyUpdate {
  label?: string;
  status?: ApiKeyStatus;
  daily_limit?: number;
}

export interface RequestEvent {
  request_id: string;
  attempt: number;
  timestamp: string;
  provider: string;
  path: string;
  method: string;
  key_id: number | null;
  key_label: string | null;
  upstream_status: number | null;
  outcome: string;
  latency_ms: number | null;
  is_retry: boolean;
  error_detail: string | null;
}

export interface GatewayTokenRead {
  id: number;
  label: string;
  token_preview: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GatewayTokenCreated {
  token: GatewayTokenRead;
  plaintext: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAdminToken()}`,
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // ignore parse errors, fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  async listKeys(): Promise<ApiKeyRead[]> {
    return request<ApiKeyRead[]>("/admin/keys");
  },

  async createKey(payload: ApiKeyCreate): Promise<ApiKeyRead> {
    return request<ApiKeyRead>("/admin/keys", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateKey(id: number, payload: ApiKeyUpdate): Promise<ApiKeyRead> {
    return request<ApiKeyRead>(`/admin/keys/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async resetCooldown(id: number): Promise<ApiKeyRead> {
    return request<ApiKeyRead>(`/admin/keys/${id}/reset-cooldown`, {
      method: "POST",
    });
  },

  async deleteKey(id: number): Promise<void> {
    return request<void>(`/admin/keys/${id}`, { method: "DELETE" });
  },

  async recentEvents(limit = 50): Promise<RequestEvent[]> {
    const data = await request<{ events: RequestEvent[] }>(
      `/admin/monitor/recent?limit=${limit}`
    );
    return data.events;
  },

  async listGatewayTokens(): Promise<GatewayTokenRead[]> {
    return request<GatewayTokenRead[]>("/admin/gateway-tokens");
  },

  async createGatewayToken(label: string): Promise<GatewayTokenCreated> {
    return request<GatewayTokenCreated>("/admin/gateway-tokens", {
      method: "POST",
      body: JSON.stringify({ label }),
    });
  },

  async revokeGatewayToken(id: number): Promise<GatewayTokenRead> {
    return request<GatewayTokenRead>(`/admin/gateway-tokens/${id}/revoke`, { method: "POST" });
  },

  async activateGatewayToken(id: number): Promise<GatewayTokenRead> {
    return request<GatewayTokenRead>(`/admin/gateway-tokens/${id}/activate`, { method: "POST" });
  },

  async deleteGatewayToken(id: number): Promise<void> {
    return request<void>(`/admin/gateway-tokens/${id}`, { method: "DELETE" });
  },

  /** Verifies the stored token actually works against the backend. */
  async verifyToken(): Promise<boolean> {
    try {
      await request("/admin/keys");
      return true;
    } catch {
      return false;
    }
  },
};

/**
 * Opens a Server-Sent Events connection to /admin/monitor/stream.
 * Native EventSource can't send custom headers, so the admin token is
 * passed as a query parameter — the backend's require_admin dependency
 * only checks the Authorization header, so we proxy this through fetch's
 * streaming body instead of EventSource for auth to work uniformly.
 */
export function streamEvents(
  onEvent: (evt: RequestEvent) => void,
  onError?: (err: unknown) => void
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/monitor/stream`, {
        headers: { Authorization: `Bearer ${getAdminToken()}` },
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";

        for (const chunk of chunks) {
          const lines = chunk.split("\n");
          let eventName = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event:")) eventName = line.slice(6).trim();
            if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (eventName === "request" && data) {
            try {
              onEvent(JSON.parse(data) as RequestEvent);
            } catch {
              // ignore malformed event
            }
          }
        }
      }
    } catch (err) {
      if ((err as any)?.name !== "AbortError") onError?.(err);
    }
  })();

  return () => controller.abort();
}
