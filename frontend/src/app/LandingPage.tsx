import { useEffect, useRef, useState } from "react";
import { KeyRound, ArrowRight, ShieldCheck, Github } from "lucide-react";

const REPO_URL = "https://github.com/Geekyup/llm-gateway";

const AMBER = "#F59E0B";
const PROVIDERS = [
  { key: "gemini", name: "Gemini", color: "#4F8EF7" },
  { key: "groq", name: "Groq", color: "#F97316" },
  { key: "openrouter", name: "OpenRouter", color: "#A78BFA" },
];

type KeyState = "active" | "exhausting" | "idle" | "cooldown";

function FailoverChain() {
  const KEYS = 5;
  const [active, setActive] = useState(0);
  const [exhausting, setExhausting] = useState<number | null>(null);
  const [cooldown, setCooldown] = useState<Set<number>>(new Set());
  const activeRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

    async function cycle() {
      while (!cancelled) {
        await sleep(2200);
        if (cancelled) return;
        const current = activeRef.current;
        setExhausting(current);
        await sleep(420);
        if (cancelled) return;

        const next = (current + 1) % KEYS;
        setCooldown((prev) => new Set(prev).add(current));
        setActive(next);
        activeRef.current = next;
        setExhausting(null);

        await sleep(4400);
        if (cancelled) return;
        setCooldown((prev) => {
          const copy = new Set(prev);
          copy.delete(current);
          return copy;
        });
      }
    }

    cycle();
    return () => {
      cancelled = true;
    };
  }, []);

  function stateFor(i: number): KeyState {
    if (exhausting === i) return "exhausting";
    if (i === active) return "active";
    if (cooldown.has(i)) return "cooldown";
    return "idle";
  }

  return (
    <div className="rounded-xl p-5 bg-card border border-border">
      <div className="flex items-center justify-between mb-4">
        <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
          key pool · any provider
        </span>
        <span
          className="text-[11px] font-mono flex items-center gap-1.5 text-primary"
          role="status"
        >
          <span className="w-1.5 h-1.5 rounded-full animate-pulse bg-primary" aria-hidden="true" />
          routing live
        </span>
      </div>

      <div className="flex items-center gap-1.5" role="img" aria-label={`Key pool status: key_0${active + 1} is currently active`}>
        {Array.from({ length: KEYS }).map((_, i) => {
          const state = stateFor(i);
          const color =
            state === "active"
              ? "var(--primary)"
              : state === "exhausting"
              ? "var(--destructive)"
              : state === "cooldown"
              ? AMBER
              : "#3F3F46";
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-2">
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-300"
                style={{
                  background: `${color}14`,
                  border: `1px solid ${color}`,
                  transform: state === "active" ? "scale(1.08)" : "scale(1)",
                  boxShadow:
                    state === "active"
                      ? `0 0 14px ${color}70`
                      : state === "exhausting"
                      ? `0 0 14px ${color}80`
                      : "0 0 0px transparent",
                }}
              >
                <KeyRound
                  size={14}
                  style={{ color }}
                  className={state === "active" ? "animate-pulse" : ""}
                />
              </div>
              <span
                className="text-[10px] font-mono"
                style={{ color: state === "idle" ? "var(--muted-foreground)" : color }}
              >
                key_0{i + 1}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-[12px] font-mono text-muted-foreground" role="status" aria-live="polite">
          {exhausting !== null ? (
            <>
              <span style={{ color: "var(--destructive)" }}>key_0{exhausting + 1}</span>{" "}
              hit its rate limit — failing over
            </>
          ) : (
            <>
              request routed to{" "}
              <span className="text-primary">key_0{active + 1}</span>
            </>
          )}
        </p>
      </div>
    </div>
  );
}

function ProviderPill({ name, color }: { name: string; color: string }) {
  return (
    <span
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-[13px] font-medium"
      style={{ color, background: `${color}14`, border: `1px solid ${color}33` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} aria-hidden="true" />
      {name}
    </span>
  );
}

function CodeToken({
  children,
  tip,
  accent,
  align = "left",
}: {
  children: React.ReactNode;
  tip: string;
  accent?: boolean;
  align?: "left" | "right";
}) {
  const [show, setShow] = useState(false);
  return (
    <span
      className="relative inline-block underline decoration-dotted cursor-help decoration-muted-foreground/50"
      style={{ color: accent ? "var(--primary)" : "inherit" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
      tabIndex={0}
    >
      {children}
      {show && (
        <span
          className={`absolute bottom-full mb-2.5 z-30 w-[240px] max-w-[80vw] whitespace-normal px-2.5 py-1.5 rounded-md text-[11px] font-mono normal-case bg-popover border border-border text-foreground ${
            align === "right" ? "right-0" : "left-0"
          }`}
          style={{ boxShadow: "0 4px 16px rgba(0,0,0,0.4)" }}
        >
          {tip}
        </span>
      )}
    </span>
  );
}

function CodeBlock() {
  return (
    <div className="rounded-xl overflow-hidden bg-popover border border-border">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border">
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--destructive)" }} />
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: AMBER }} />
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--primary)" }} />
        <span className="ml-2 text-[11px] font-mono text-muted-foreground">request.sh</span>
        <span className="ml-auto text-[10px] font-mono text-muted-foreground hidden sm:inline">
          hover the underlined bits
        </span>
      </div>
      <div className="overflow-x-auto">
        <pre className="px-4 pt-10 pb-4 text-[12.5px] font-mono leading-relaxed text-foreground w-max min-w-full">
          {"curl https://api.your-gateway.dev/v1/chat/completions \\\n  -H \""}
          <CodeToken
            tip="Bearer + your gateway token, from Account -> Gateway tokens"
            accent
          >
            Authorization: Bearer $GATEWAY_TOKEN
          </CodeToken>
          {'" \\\n  -d \'{\n    "model": "'}
          <CodeToken
            tip="Any model any of your pooled providers serves. Omit it and Keypool picks from whatever's active."
            align="right"
          >
            gemini-2.0-flash
          </CodeToken>
          {'",\n    "messages": [{ "role": "user", "content": "hi" }]\n  }\''}
        </pre>
      </div>
    </div>
  );
}

type FeedRow = { provider: string; color: string; model: string; ms: number; status: string };

const FEED_POOL: FeedRow[] = [
  { provider: "gemini", color: "#4F8EF7", model: "gemini-2.0-flash", ms: 412, status: "ok" },
  { provider: "groq", color: "#F97316", model: "llama-3.3-70b", ms: 189, status: "ok" },
  { provider: "gemini", color: "#4F8EF7", model: "gemini-2.0-flash", ms: 3, status: "429 → retry" },
  { provider: "openrouter", color: "#A78BFA", model: "claude-3-5-haiku", ms: 731, status: "ok" },
  { provider: "groq", color: "#F97316", model: "llama-3.1-8b", ms: 94, status: "ok" },
  { provider: "openrouter", color: "#A78BFA", model: "gpt-4o-mini", ms: 512, status: "ok" },
  { provider: "gemini", color: "#4F8EF7", model: "gemini-1.5-pro", ms: 288, status: "ok" },
];

function useLiveFeed(size = 4, intervalMs = 2600) {
  const [rows, setRows] = useState<FeedRow[]>(() => FEED_POOL.slice(0, size));
  const cursor = useRef(size % FEED_POOL.length);

  useEffect(() => {
    const id = setInterval(() => {
      const next = FEED_POOL[cursor.current % FEED_POOL.length];
      cursor.current += 1;
      setRows((prev) => [next, ...prev.slice(0, size - 1)]);
    }, intervalMs);
    return () => clearInterval(id);
  }, [size, intervalMs]);

  return rows;
}

function SignInButton({
  onClick,
  size = "md",
  showArrow = false,
}: {
  onClick: () => void;
  size?: "sm" | "md";
  showArrow?: boolean;
}) {
  const [pending, setPending] = useState(false);
  const padding = size === "sm" ? "px-3.5 py-1.5 text-[13px]" : "px-5 py-2.5 text-[14px]";

  function handleClick() {
    if (pending) return;
    setPending(true);
    onClick();
  }

  return (
    <button
      onClick={handleClick}
      disabled={pending}
      aria-busy={pending}
      className={`group font-medium rounded-md flex items-center gap-2 transition-all active:scale-[0.97] disabled:opacity-70 disabled:cursor-not-allowed ${padding}`}
      style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
    >
      {pending ? "Redirecting…" : "Sign in with Google"}
      {showArrow && !pending && (
        <ArrowRight
          size={15}
          className="transition-transform duration-200 group-hover:translate-x-0.5"
        />
      )}
    </button>
  );
}

export default function LandingPage({ onSignIn }: { onSignIn: () => void }) {
  const feedRows = useLiveFeed();

  return (
    <div className="min-h-screen w-full bg-background text-foreground">
      <div className="relative">
        <div className="absolute inset-0 hero-grid pointer-events-none" />

        <header className="sticky top-0 z-10 backdrop-blur-sm border-b border-border" style={{ background: "rgba(10,10,11,0.8)" }}>
          <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
            <div className="flex items-center">
              <span className="font-mono font-semibold tracking-tight" style={{ fontSize: "22px" }}>
                <span>key</span>
                <span className="text-primary">pool</span>
              </span>
            </div>
            <div className="flex items-center gap-3">
              <a
                href={REPO_URL}
                target="_blank"
                rel="noreferrer noopener"
                aria-label="View source on GitHub"
                className="flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground transition-colors"
              >
                <Github size={15} />
                <span className="hidden sm:inline">Source</span>
              </a>
              <SignInButton onClick={onSignIn} size="sm" />
            </div>
          </div>
        </header>

        <section className="relative max-w-5xl mx-auto px-6 pt-20 pb-16">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <p className="text-[11px] font-mono uppercase tracking-wider mb-4 text-muted-foreground">
                self-hosted / v0.4
              </p>
              <h1 className="text-[34px] md:text-[42px] leading-[1.1] font-semibold tracking-tight mb-5">
                One endpoint. Many keys.{" "}
                <span className="sm:block">Zero 429s reaching your app.</span>
              </h1>
              <p className="text-[15px] leading-relaxed mb-8 max-w-md text-muted-foreground">
                Keypool sits between your app and Gemini, Groq, or OpenRouter.
                It holds your keys, rotates them per request, and retries on a
                different key the moment one gets rate limited — same request
                and response shape as the OpenAI API.
              </p>
              <div className="flex items-center gap-3">
                <SignInButton onClick={onSignIn} showArrow />
                <span className="text-[12px] font-mono text-muted-foreground">
                  self-serve, no sales call
                </span>
              </div>
            </div>
            <FailoverChain />
          </div>
        </section>
      </div>

      <section className="max-w-5xl mx-auto px-6 py-10 border-t border-border">
        <p className="text-[11px] font-mono uppercase tracking-wider mb-4 text-muted-foreground">
          Supported providers
        </p>
        <div className="flex flex-wrap gap-3">
          {PROVIDERS.map((p) => (
            <ProviderPill key={p.key} name={p.name} color={p.color} />
          ))}
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-6 pb-16">
        <div className="grid md:grid-cols-[1.1fr_0.9fr] gap-8 items-start">
          <div className="rounded-xl overflow-hidden bg-card border border-border">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
              <span className="text-[11px] font-mono text-muted-foreground">live request feed</span>
              <span
                className="text-[10px] font-mono flex items-center gap-1.5 text-primary"
                role="status"
                aria-live="polite"
              >
                <span className="w-1 h-1 rounded-full animate-pulse bg-primary" />
                sse
              </span>
            </div>
            <div className="divide-y divide-border">
              {feedRows.map((r, i) => (
                <div key={i} className="px-4 py-2.5 flex items-center gap-3 text-[12px] font-mono">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: r.color }} />
                  <span className="w-20 shrink-0" style={{ color: r.color }}>
                    {r.provider}
                  </span>
                  <span className="flex-1 truncate text-muted-foreground">{r.model}</span>
                  <span className="w-14 text-right text-muted-foreground">{r.ms}ms</span>
                  <span
                    className="w-16 text-right"
                    style={{ color: r.status === "ok" ? "var(--muted-foreground)" : AMBER }}
                  >
                    {r.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-[18px] font-medium tracking-tight mb-4">What it actually does</h2>
            <ul className="space-y-3.5 text-[13px] leading-relaxed text-muted-foreground">
              <li>
                <span className="text-foreground">Key pooling.</span> Add every key
                you have per provider — Keypool round-robins across them
                instead of one key eating the whole rate limit.
              </li>
              <li>
                <span className="text-foreground">Failover mid-request.</span> A
                429 or exhausted key doesn't reach your app; the request
                retries on the next available key.
              </li>
              <li>
                <span className="text-foreground">OpenAI request shape.</span>{" "}
                Same <code className="font-mono text-[12px]">/v1/chat/completions</code> body
                and response fields — change the base URL, not your code.
              </li>
              <li>
                <span className="text-foreground">Per-key limits and pinning.</span>{" "}
                Cap daily usage per key, or pin a key to a specific model.
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="grid md:grid-cols-2 gap-10 items-center">
          <div>
            <h2 className="text-[18px] font-medium tracking-tight mb-3">
              Same request you already write
            </h2>
            <p className="text-[13px] leading-relaxed mb-4 text-muted-foreground">
              Point your existing OpenAI client at your gateway URL and a
              gateway token. Nothing else in your integration changes.
            </p>
            <div className="flex items-center gap-2 text-[12px] font-mono text-muted-foreground">
              <ShieldCheck size={13} className="text-primary" />
              Provider keys are encrypted at rest, never sent to the client
            </div>
          </div>
          <CodeBlock />
        </div>
      </section>

      <footer className="max-w-5xl mx-auto px-6 py-6 text-[12px] font-mono flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between text-muted-foreground border-t border-border">
        <div className="flex items-center gap-4">
          <span className="font-semibold">
            <span>key</span>
            <span className="text-primary">pool</span>
          </span>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="flex items-center gap-1.5 hover:text-foreground transition-colors"
          >
            <Github size={13} />
            source
          </a>
        </div>
        <span>each account manages its own keys, tokens, and request history</span>
      </footer>
    </div>
  );
}