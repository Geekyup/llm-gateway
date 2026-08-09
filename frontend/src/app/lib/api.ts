export const API_BASE_URL: string =
  (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8000";

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

export function startGoogleLogin(): void {
  window.location.href = `${API_BASE_URL}/auth/google/login`;
}

export type ApiKeyStatus = "active" | "cooldown" | "exhausted" | "disabled";
export type ApiProvider = "gemini" | "openrouter" | "groq";

export interface ApiKeyRead {
  id: number;
  label: string;
  provider: ApiProvider;
  status: ApiKeyStatus;
  requests_today: number;
  daily_limit: number;
  model: string | null;
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
  model?: string | null;
}

export interface ApiKeyUpdate {
  label?: string;
  status?: ApiKeyStatus;
  daily_limit?: number;
  model?: string | null;
}

export interface ModelOption {
  id: string;
  label: string;
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
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export interface ApiKeyHealthCheckResult {
  key_id: number;
  ok: boolean;
  detail: string | null;
}

export interface HourlyUsagePoint {
  hour: number;
  requests: number;
}

export interface HourlyUsageResponse {
  key_id: number;
  points: HourlyUsagePoint[];
}

export interface HourlyTokenPoint {
  hour: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface HourlyTokenUsageResponse {
  key_id: number;
  points: HourlyTokenPoint[];
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
  const res = await fetch(`${API_BASE_URL}${path}`, {
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
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  async listKeys(): Promise<ApiKeyRead[]> {
    return request<ApiKeyRead[]>("/me/keys");
  },

  async createKey(payload: ApiKeyCreate): Promise<ApiKeyRead> {
    return request<ApiKeyRead>("/me/keys", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async listModels(provider: ApiProvider, rawKey: string): Promise<ModelOption[]> {
    const res = await request<{ models: ModelOption[] }>("/me/keys/list-models", {
      method: "POST",
      body: JSON.stringify({ provider, raw_key: rawKey }),
    });
    return res.models;
  },

  async updateKey(id: number, payload: ApiKeyUpdate): Promise<ApiKeyRead> {
    return request<ApiKeyRead>(`/me/keys/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async resetCooldown(id: number): Promise<ApiKeyRead> {
    return request<ApiKeyRead>(`/me/keys/${id}/reset-cooldown`, {
      method: "POST",
    });
  },

  async deleteKey(id: number): Promise<void> {
    return request<void>(`/me/keys/${id}`, { method: "DELETE" });
  },

  async checkKey(id: number): Promise<ApiKeyHealthCheckResult> {
    return request<ApiKeyHealthCheckResult>(`/me/keys/${id}/check`, { method: "POST" });
  },

  async checkAllKeys(): Promise<ApiKeyHealthCheckResult[]> {
    return request<ApiKeyHealthCheckResult[]>("/me/keys/check-all", { method: "POST" });
  },

  async hourlyUsage(id: number): Promise<HourlyUsageResponse> {
    return request<HourlyUsageResponse>(`/me/keys/${id}/hourly-usage`);
  },

  async hourlyTokenUsage(id: number): Promise<HourlyTokenUsageResponse> {
    return request<HourlyTokenUsageResponse>(`/me/keys/${id}/hourly-token-usage`);
  },

  async recentEvents(limit = 50): Promise<RequestEvent[]> {
    const data = await request<{ events: RequestEvent[] }>(
      `/me/monitor/recent?limit=${limit}`
    );
    return data.events;
  },

  async listGatewayTokens(): Promise<GatewayTokenRead[]> {
    return request<GatewayTokenRead[]>("/me/gateway-tokens");
  },

  async createGatewayToken(label: string): Promise<GatewayTokenCreated> {
    return request<GatewayTokenCreated>("/me/gateway-tokens", {
      method: "POST",
      body: JSON.stringify({ label }),
    });
  },

  async revokeGatewayToken(id: number): Promise<GatewayTokenRead> {
    return request<GatewayTokenRead>(`/me/gateway-tokens/${id}/revoke`, { method: "POST" });
  },

  async activateGatewayToken(id: number): Promise<GatewayTokenRead> {
    return request<GatewayTokenRead>(`/me/gateway-tokens/${id}/activate`, { method: "POST" });
  },

  async deleteGatewayToken(id: number): Promise<void> {
    return request<void>(`/me/gateway-tokens/${id}`, { method: "DELETE" });
  },

  async me(): Promise<UserRead> {
    return request<UserRead>("/auth/me");
  },

  async logout(): Promise<void> {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return;
    try {
      await request<void>("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
    }
  },
};

export interface PlaygroundChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatStreamHandlers {
  onDelta: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

/**
 * Streams a chat completion from the built-in playground endpoint, which is
 * authenticated with the user's normal session — no gateway token needed.
 */
export async function streamPlaygroundChat(
  params: { messages: PlaygroundChatMessage[]; provider?: string; model?: string },
  handlers: ChatStreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/me/playground/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getAccessToken()}`,
      },
      body: JSON.stringify({ ...params, stream: true }),
      signal,
    });
  } catch (err) {
    handlers.onError(err instanceof Error ? err.message : "Network error");
    return;
  }

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return streamPlaygroundChat(params, handlers, signal);
    }
    clearTokenPair();
    handlers.onError("Session expired — please sign in again");
    return;
  }

  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body.error?.message ?? JSON.stringify(body);
    } catch {
    }
    handlers.onError(detail || `Request failed (${res.status})`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part.split("\n").find(l => l.startsWith("data:"));
      if (!line) continue;
      const data = line.slice(5).trim();
      if (!data) continue;
      if (data === "[DONE]") {
        handlers.onDone();
        return;
      }
      try {
        const parsed = JSON.parse(data);
        if (parsed?.error?.message) {
          handlers.onError(parsed.error.message);
          return;
        }
        const delta: string | undefined = parsed?.choices?.[0]?.delta?.content;
        if (delta) handlers.onDelta(delta);
      } catch {
      }
    }
  }
  handlers.onDone();
}

export function streamEvents(
  onEvent: (evt: RequestEvent) => void,
  onError?: (err: unknown) => void
): () => void {
  const controller = new AbortController();
  let stopped = false;
  let retryDelayMs = 1000;

  async function connect() {
    while (!stopped) {
      try {
        const res = await fetch(`${API_BASE_URL}/me/monitor/stream`, {
          headers: { Authorization: `Bearer ${getAccessToken()}` },
          signal: controller.signal,
        });

        if (res.status === 401) {
          const refreshed = await tryRefresh();
          if (!refreshed) {
            clearTokenPair();
            onError?.(new Error("session expired"));
            return;
          }
          continue;
        }

        if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        retryDelayMs = 1000;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          buffer = buffer.replace(/\r\n/g, "\n");

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
              }
            }
          }
        }
      } catch (err) {
        if ((err as any)?.name === "AbortError" || stopped) return;
        onError?.(err);
      }

      if (stopped) return;
      await new Promise(r => setTimeout(r, retryDelayMs));
      retryDelayMs = Math.min(retryDelayMs * 2, 15000);
    }
  }

  connect();

  return () => {
    stopped = true;
    controller.abort();
  };
}