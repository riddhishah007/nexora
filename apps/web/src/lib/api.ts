const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("nexora_token");
}

export function setToken(token: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem("nexora_token", token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("nexora_token");
}

export async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers,
  });

  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const j = JSON.parse(text);
      detail = j.detail || j.message || text;
    } catch {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  // 204 No Content
  if (res.status === 204) return null as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

// --- typed helpers ---
export type AgentInfo = {
  agent_id: string;
  name: string;
  description: string;
  capabilities: string[];
  supported_tasks: string[];
  tools: string[];
  permissions: string[];
  model: string;
  status: string;
};

export type WorkflowStep = {
  seq: number;
  agent_id: string;
  instruction: string;
  depends_on: number[];
  status: string;
  output?: Record<string, unknown> | null;
};

export type Workflow = {
  id: string;
  name: string;
  status: string;
  steps: WorkflowStep[];
  definition?: Record<string, unknown> | null;
};

export type Template = {
  id: string;
  name: string;
  description: string;
  steps: { agent_id: string; instruction: string; depends_on: number[] }[];
};

// --- chat workspace ---
export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  workflow_id?: string | null;
};

export type ConversationDetail = ConversationSummary & {
  messages: ChatMessage[];
};

export type ChatResponse = {
  conversation_id: string;
  workflow_id: string;
  status: string;
  steps: {
    seq: number;
    agent_id: string;
    instruction: string;
    depends_on: number[];
    status: string;
  }[];
};
