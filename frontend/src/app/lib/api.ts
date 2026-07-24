// ─── API client for llm-gateway backend ────────────────────────────────────
// Talks to /me/keys* and /me/monitor* on the FastAPI backend.
// Auth is Google OAuth: the backend issues a JWT access/refresh pair after
// /auth/google/callback, which lands back on the frontend with the
// pair in the URL fragment (#access_token=...&refresh_token=...).

// Normalized to never end in a trailing slash, so every call site below can
// safely do `${API_BASE_URL}/some/path` without risking `//` or a missing
// separator depending on how VITE_API_URL happens to be configured.
export const API_BASE_URL: string = (
  (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

const ACCESS_TOKEN_KEY = "llm_gateway_access_token";
const REFRESH_TOKEN_KEY = "llm_gateway_refresh_token";

export function getAccessToken(): string {
  return localStorage.getItem(ACCESS_TOKEN_KEY) ?? "";
}

export function getRefreshToken(): string {
  return localStorage.getItem(REFRESH_TOKEN_KEY) ?? "";
}

export function setTokenPair(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokenPair(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/** Redirects the whole page to Google's consent screen via the backend. */
export function startGoogleLogin(): void {
  window.location.href = `${API_BASE_URL}/auth/google/login`;
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
  user_id: number;
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

export interface ApiKeyHealthCheckResult {
  key_id: number;
  ok: boolean;
  detail: string | null;
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

export interface UserRead {
  id: number;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let refreshInFlight: Promise<boolean> | null = null;

/** Exchanges the stored refresh token for a new pair. Single-flight so
 * concurrent 401s don't each fire their own refresh call.
 */
async function tryRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refreshToken = getRefreshToken();
      if (!refreshToken) return false;
      try {
        const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) return false;
        const pair = await res.json();
        setTokenPair(pair.access_token, pair.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

async function request<T>(path: string, init?: RequestInit, _retried = false): Promise<T> {
  const res = await fetch(`${API_BASE_URL}/${path.replace(/^\/+/, "")}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAccessToken()}`,
      ...(init?.headers ?? {}),
    },
  });

  if (res.status === 401 && !_retried) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, init, true);
    clearTokenPair();
  }

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
    return request<ApiKeyRead[]>("me/keys");
  },

  async createKey(payload: ApiKeyCreate): Promise<ApiKeyRead> {
    return request<ApiKeyRead>("me/keys", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateKey(id: number, payload: ApiKeyUpdate): Promise<ApiKeyRead> {
    return request<ApiKeyRead>(`me/keys/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async resetCooldown(id: number): Promise<ApiKeyRead> {
    return request<ApiKeyRead>(`me/keys/${id}/reset-cooldown`, {
      method: "POST",
    });
  },

  async deleteKey(id: number): Promise<void> {
    return request<void>(`me/keys/${id}`, { method: "DELETE" });
  },

  async checkKey(id: number): Promise<ApiKeyHealthCheckResult> {
    return request<ApiKeyHealthCheckResult>(`me/keys/${id}/check`, { method: "POST" });
  },

  async checkAllKeys(): Promise<ApiKeyHealthCheckResult[]> {
    return request<ApiKeyHealthCheckResult[]>("me/keys/check-all", { method: "POST" });
  },

  async recentEvents(limit = 50): Promise<RequestEvent[]> {
    const data = await request<{ events: RequestEvent[] }>(
      `me/monitor/recent?limit=${limit}`
    );
    return data.events;
  },

  async listGatewayTokens(): Promise<GatewayTokenRead[]> {
    return request<GatewayTokenRead[]>("me/gateway-tokens");
  },

  async createGatewayToken(label: string): Promise<GatewayTokenCreated> {
    return request<GatewayTokenCreated>("me/gateway-tokens", {
      method: "POST",
      body: JSON.stringify({ label }),
    });
  },

  async revokeGatewayToken(id: number): Promise<GatewayTokenRead> {
    return request<GatewayTokenRead>(`me/gateway-tokens/${id}/revoke`, { method: "POST" });
  },

  async activateGatewayToken(id: number): Promise<GatewayTokenRead> {
    return request<GatewayTokenRead>(`me/gateway-tokens/${id}/activate`, { method: "POST" });
  },

  async deleteGatewayToken(id: number): Promise<void> {
    return request<void>(`me/gateway-tokens/${id}`, { method: "DELETE" });
  },

  /** Fetches the signed-in user's profile — also doubles as an auth check. */
  async me(): Promise<UserRead> {
    return request<UserRead>("auth/me");
  },

  async logout(): Promise<void> {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return;
    try {
      await request<void>("auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // best-effort — clear local tokens regardless of server response
    }
  },
};

/**
 * Opens a Server-Sent Events connection to /me/monitor/stream.
 * Native EventSource can't send custom headers, so this is proxied through
 * fetch's streaming body instead, same as the rest of the client.
 */
export function streamEvents(
  onEvent: (evt: RequestEvent) => void,
  onError?: (err: unknown) => void
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/me/monitor/stream`, {
        headers: { Authorization: `Bearer ${getAccessToken()}` },
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