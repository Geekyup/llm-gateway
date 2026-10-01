import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { KeyRound, Plus, MessageSquare, User, Bot, AlertTriangle, Trash2, Square, ArrowUp } from "lucide-react";
import { streamPlaygroundChat, type PlaygroundChatMessage } from "../../lib/api";
import type { AK, Provider } from "../../types";
import { ModelPill } from "./ModelPill";
import { MessageActions } from "./MessageActions";
import { CodeBlock } from "../shared/CodeBlock";

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
          className="flex flex-col items-center text-center gap-4 px-8 py-12 rounded-lg w-full max-w-md"
          style={{ background: "var(--background)", border: "1px solid var(--field)" }}
        >
          <div
            className="w-14 h-14 rounded-lg flex items-center justify-center relative"
            style={{ background: "color-mix(in srgb, var(--accent) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--accent) 20%, transparent)" }}
          >
            <KeyRound size={22} color="var(--accent)" />
            <div
              className="absolute -bottom-1 -right-1 w-[22px] h-[22px] rounded-full flex items-center justify-center"
              style={{ background: "var(--field)", border: "2px solid var(--background)" }}
            >
              <Plus size={12} color="var(--ink-3)" />
            </div>
          </div>

          <div>
            <div className="text-sm font-medium text-ink">No active keys yet</div>
            <div className="text-xs mt-1.5 max-w-xs" style={{ color: "var(--ink-3)" }}>
              Add an API key from a provider to start testing prompts right here in the playground.
            </div>
          </div>

          <button
            onClick={onAddKey}
            className="mt-1 flex items-center gap-1.5 text-xs font-medium px-4 py-2 rounded-lg transition-opacity hover:opacity-90"
            style={{ background: "var(--accent)", color: "var(--on-accent)" }}
          >
            <Plus size={14} />
            Add API key
          </button>
        </div>
      </div>
    );
  }

  async function runCompletion(nextMessages: PlaygroundChatMessage[]) {
    setError(null);
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

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    await runCompletion([...messages, { role: "user", content: text }]);
  }

  async function regenerate(assistantIndex: number) {
    if (streaming) return;
    const prior = messages.slice(0, assistantIndex);
    await runCompletion(prior);
  }

  function stop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  const [focused, setFocused] = useState(false);

  return (
    <div className="flex flex-col mx-auto w-full max-w-3xl playground-shell">
      <div className="flex-1 overflow-y-auto thin-scrollbar px-1 sm:px-2">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4" style={{ color: "var(--ink-4)" }}>
            <div className="w-11 h-11 rounded-lg flex items-center justify-center" style={{ background: "color-mix(in srgb, var(--accent) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--accent) 20%, transparent)" }}>
              <MessageSquare size={18} color="var(--accent)" />
            </div>
            <div className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Test your key pool</div>
            <div className="text-xs max-w-xs">Send a message below — it goes through the same failover and retry logic as any client of the gateway.</div>
          </div>
        ) : (
          <div className="py-6 sm:py-8 space-y-7 sm:space-y-8">
            {messages.map((m, i) => {
              const isLastAssistant = m.role === "assistant" && i === messages.length - 1;
              const isPending = streaming && isLastAssistant && !m.content;
              return (
                <div key={i} className="group flex gap-2.5 sm:gap-3" style={{ opacity: isPending ? 0.65 : 1 }}>
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                    style={{
                      background: m.role === "user" ? "color-mix(in srgb, var(--ink) 10%, transparent)" : "color-mix(in srgb, var(--accent) 12%, transparent)",
                      border: m.role === "user" ? "1px solid color-mix(in srgb, var(--ink) 14%, transparent)" : "1px solid color-mix(in srgb, var(--accent) 20%, transparent)",
                    }}
                  >
                    {m.role === "user" ? <User size={13} color="var(--ink-2)" /> : <Bot size={13} color="var(--accent)" />}
                  </div>
                  <div className="min-w-0 flex-1 pt-1">
                    <div className="text-[12px] font-medium mb-1.5" style={{ color: "var(--ink-4)" }}>
                      {m.role === "user" ? "You" : "Assistant"}
                    </div>
                    {m.content ? (
                      <div className="markdown-body">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[rehypeHighlight]}
                          components={{
                            pre: ({ children }) => <>{children}</>,
                            code: ({ className, children, ...props }) => {
                              const isBlock = /language-/.test(className ?? "");
                              if (!isBlock) {
                                return (
                                  <code className={className} {...props}>
                                    {children}
                                  </code>
                                );
                              }
                              return <CodeBlock className={className}>{children}</CodeBlock>;
                            },
                          }}
                        >
                          {m.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="text-sm leading-relaxed flex items-center h-5" style={{ color: "var(--ink-2)" }}>
                        {isPending && <span className="typing-dots" aria-label="Generating" />}
                      </div>
                    )}
                    {m.content && !isPending && (
                      <MessageActions
                        content={m.content}
                        onRegenerate={m.role === "assistant" && !streaming ? () => regenerate(i) : undefined}
                        className="mt-1.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 sm:opacity-0"
                      />
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 px-3.5 py-2 mb-2 mx-1 sm:mx-2 rounded-lg text-xs shrink-0" style={{ color: "var(--bad)", background: "color-mix(in srgb, var(--bad) 8%, transparent)", border: "1px solid color-mix(in srgb, var(--bad) 15%, transparent)" }}>
          <AlertTriangle size={12} className="shrink-0" /> {error}
        </div>
      )}

      <div className="shrink-0 pb-3 sm:pb-6 px-1 sm:px-0 playground-composer-wrap">
        <div
          className="rounded-lg overflow-visible transition-shadow duration-150"
          style={{
            background: "var(--field)",
            border: focused ? "1px solid color-mix(in srgb, var(--accent) 35%, transparent)" : "1px solid color-mix(in srgb, var(--ink) 15%, transparent)",
            boxShadow: focused ? "0 0 0 3px color-mix(in srgb, var(--accent) 8%, transparent), 0 8px 24px rgba(26,26,24,0.17)" : "0 4px 16px rgba(26,26,24,0.11)",
          }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Message the gateway…"
            disabled={streaming}
            rows={1}
            className="w-full resize-none px-4 pt-3.5 pb-2 outline-none bg-transparent playground-textarea"
            style={{ color: "var(--ink)", maxHeight: 200 }}
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

            <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
              {messages.length > 0 && (
                <button onClick={() => setMessages([])} title="Clear chat" type="button" className="playground-icon-btn rounded-full transition-colors hover:bg-ink/5">
                  <Trash2 size={13} color="var(--ink-4)" />
                </button>
              )}
              {streaming ? (
                <button onClick={stop} type="button" className="playground-icon-btn playground-send-btn rounded-full shrink-0 transition-all active:scale-95" style={{ background: "color-mix(in srgb, var(--bad) 12%, transparent)", border: "1px solid color-mix(in srgb, var(--bad) 30%, transparent)" }}>
                  <Square size={12} color="var(--bad)" />
                </button>
              ) : (
                <button
                  onClick={send}
                  disabled={!input.trim()}
                  type="button"
                  className="playground-icon-btn playground-send-btn rounded-full shrink-0 transition-all active:scale-95 disabled:scale-100"
                  style={{
                    background: input.trim() ? "var(--accent)" : "color-mix(in srgb, var(--ink) 14%, transparent)",
                    boxShadow: input.trim() ? "0 2px 10px color-mix(in srgb, var(--accent) 35%, transparent)" : "none",
                  }}
                >
                  <ArrowUp size={15} color={input.trim() ? "var(--on-accent)" : "var(--ink-4)"} strokeWidth={2.5} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}