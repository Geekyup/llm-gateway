import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { KeyRound, Plus, MessageSquare, User, Bot, AlertTriangle, Trash2, Square, Send } from "lucide-react";
import { streamPlaygroundChat, type PlaygroundChatMessage } from "../../lib/api";
import type { AK, Provider } from "../../types";
import { ModelPill } from "./ModelPill";

export function ChatPlayground({ keys, active, onAddKey }: { keys: AK[]; active: boolean; onAddKey?: () => void }) {
  const activeKeys = keys.filter((k) => k.status !== "disabled");
  const providers = Array.from(new Set(activeKeys.map((k) => k.provider))) as Provider[];

  const [provider, setProvider] = useState<Provider | "">(providers[0] ?? "");
  const [model, setModel] = useState<string>("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<PlaygroundChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (provider && !providers.includes(provider as Provider)) setProvider(providers[0] ?? "");
  }, [providers, provider]);

  const modelsForProvider = Array.from(
    new Set(activeKeys.filter((k) => k.provider === provider && k.model).map((k) => k.model as string))
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    const resize = () => {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    };
    const raf = requestAnimationFrame(resize);
    return () => cancelAnimationFrame(raf);
  }, [input, active]);

  if (providers.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <div
          className="flex flex-col items-center text-center gap-4 px-8 py-12 rounded-2xl w-full max-w-md"
          style={{ background: "#0A0A0B", border: "1px solid #232326" }}
        >
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center relative"
            style={{ background: "rgba(0,214,143,0.1)", border: "1px solid rgba(0,214,143,0.2)" }}
          >
            <KeyRound size={22} color="#00D68F" />
            <div
              className="absolute -bottom-1 -right-1 w-[22px] h-[22px] rounded-full flex items-center justify-center"
              style={{ background: "#18181B", border: "2px solid #0A0A0B" }}
            >
              <Plus size={12} color="#71717A" />
            </div>
          </div>

          <div>
            <div className="text-sm font-medium text-zinc-100">No active keys yet</div>
            <div className="text-xs mt-1.5 max-w-xs" style={{ color: "#71717A" }}>
              Add an API key from a provider to start testing prompts right here in the playground.
            </div>
          </div>

          <button
            onClick={onAddKey}
            className="mt-1 flex items-center gap-1.5 text-xs font-medium px-4 py-2 rounded-lg transition-opacity hover:opacity-90"
            style={{ background: "#00D68F", color: "#06281E" }}
          >
            <Plus size={14} />
            Add API key
          </button>
        </div>
      </div>
    );
  }

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    setError(null);
    setInput("");
    const nextMessages: PlaygroundChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages([...nextMessages, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    await streamPlaygroundChat(
      { messages: nextMessages, provider: provider || undefined, model: model || undefined },
      {
        onDelta: (delta) => {
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { role: "assistant", content: copy[copy.length - 1].content + delta };
            return copy;
          });
        },
        onDone: () => setStreaming(false),
        onError: (message) => {
          setError(message);
          setStreaming(false);
          setMessages((prev) => prev.slice(0, -1));
        },
      },
      controller.signal
    );
  }

  function stop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  return (
    <div className="flex flex-col mx-auto w-full max-w-3xl" style={{ height: "calc(100vh - 130px)" }}>
      <div className="flex-1 overflow-y-auto thin-scrollbar pr-2">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center" style={{ color: "#3F3F46" }}>
            <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: "rgba(0,214,143,0.1)", border: "1px solid rgba(0,214,143,0.2)" }}>
              <MessageSquare size={18} color="#00D68F" />
            </div>
            <div className="text-sm font-medium" style={{ color: "#A1A1AA" }}>Test your key pool</div>
            <div className="text-xs max-w-xs">Send a message below — it goes through the same failover and retry logic as any client of the gateway.</div>
          </div>
        ) : (
          <div className="py-6 space-y-6">
            {messages.map((m, i) => (
              <div key={i} className="flex gap-3" style={{ opacity: streaming && i === messages.length - 1 && !m.content ? 0.6 : 1 }}>
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                  style={{
                    background: m.role === "user" ? "rgba(255,255,255,0.06)" : "rgba(0,214,143,0.12)",
                    border: m.role === "user" ? "1px solid rgba(255,255,255,0.08)" : "1px solid rgba(0,214,143,0.2)",
                  }}
                >
                  {m.role === "user" ? <User size={13} color="#A1A1AA" /> : <Bot size={13} color="#00D68F" />}
                </div>
                <div className="min-w-0 flex-1 pt-1">
                  <div className="text-[11px] font-medium mb-1" style={{ color: "#52525B" }}>
                    {m.role === "user" ? "You" : "Assistant"}
                  </div>
                  {m.content ? (
                    <div className="markdown-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                        {m.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="text-sm leading-relaxed" style={{ color: "#DCDCE1" }}>
                      {streaming && i === messages.length - 1 ? "···" : ""}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 px-3.5 py-2 mb-2 rounded-lg text-xs shrink-0" style={{ color: "#EF4444", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.15)" }}>
          <AlertTriangle size={12} className="shrink-0" /> {error}
        </div>
      )}

      <div className="shrink-0 pb-4 sm:pb-6">
        <div className="rounded-2xl overflow-visible" style={{ background: "#18181B", border: "1px solid rgba(255,255,255,0.09)" }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="Message the gateway…"
            disabled={streaming}
            rows={1}
            className="w-full resize-none px-4 pt-3.5 pb-2 text-sm outline-none bg-transparent"
            style={{ color: "#ECECF0", maxHeight: 200 }}
          />

          <div className="flex items-center justify-between gap-2 px-3 pb-2.5">
            {provider ? (
              <div className="min-w-0 flex-1">
                <ModelPill
                  provider={provider as Provider}
                  model={model}
                  providers={providers}
                  modelsForProvider={modelsForProvider}
                  onProvider={(p) => { setProvider(p); setModel(""); }}
                  onModel={setModel}
                />
              </div>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-1.5 shrink-0">
              {messages.length > 0 && (
                <button onClick={() => setMessages([])} title="Clear chat" className="p-1.5 rounded-full transition-colors hover:bg-white/5">
                  <Trash2 size={13} color="#52525B" />
                </button>
              )}
              {streaming ? (
                <button onClick={stop} className="flex items-center justify-center w-8 h-8 rounded-full shrink-0 transition-all active:scale-95" style={{ background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.3)" }}>
                  <Square size={12} color="#EF4444" />
                </button>
              ) : (
                <button onClick={send} disabled={!input.trim()} className="flex items-center justify-center w-8 h-8 rounded-full shrink-0 transition-all active:scale-95 disabled:opacity-30" style={{ background: "#00D68F" }}>
                  <Send size={12} color="#0A0A0B" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}