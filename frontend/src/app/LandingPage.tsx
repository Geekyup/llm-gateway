import { useEffect, useRef, useState } from "react";
import { KeyRound, ArrowRight, ShieldCheck } from "lucide-react";

// -----------------------------------------------------------------------
// Colors here are pulled 1:1 from src/styles/theme.css (--primary,
// --destructive, --chart-2..5, etc). Nothing is a new hex value.
// -----------------------------------------------------------------------
const AMBER = "#F59E0B";
const PROVIDERS = [
  { key: "gemini", name: "Gemini", color: "#4F8EF7" },
  { key: "groq", name: "Groq", color: "#F97316" },
  { key: "openrouter", name: "OpenRouter", color: "#A78BFA" },
];

type KeyState = "active" | "exhausting" | "idle" | "cooldown";

// -----------------------------------------------------------------------
// Signature element: a live failover chain. One key is active at a time;
// every few seconds it "exhausts" (flashes red) and the baton visibly
// passes to the next key. This is the one concrete thing the product
// does, shown instead of described.
// -----------------------------------------------------------------------
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
          key pool · gemini
        </span>
        <span className="text-[11px] font-mono flex items-center gap-1.5 text-primary">
          <span className="w-1.5 h-1.5 rounded-full animate-pulse bg-primary" />
          routing live
        </span>
      </div>

      <div className="flex items-center gap-1.5">
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
        <p className="text-[12px] font-mono text-muted-foreground">
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
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {name}
    </span>
  );
}

function CodeToken({
  children,
  tip,
  accent,
}: {
  children: React.ReactNode;
  tip: string;
  accent?: boolean;
}) {
  const [show, setShow] = useState(false);
  return (
    <span
      className="relative inline-block underline decoration-dotted cursor-help decoration-muted-foreground/50"
      style={{ color: accent ? "var(--primary)" : "inherit" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          className="absolute left-0 bottom-full mb-2 z-20 whitespace-nowrap px-2.5 py-1.5 rounded-md text-[11px] font-mono normal-case bg-popover border border-border text-foreground"
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
      <pre className="px-4 py-4 text-[12.5px] font-mono leading-relaxed overflow-x-auto text-foreground">
        {"curl https://api.your-gateway.dev/v1/chat/completions \\\n  -H \""}
        <CodeToken
          tip="Bearer + your gateway token, from Account -> Gateway tokens. Not a provider key."
          accent
        >
          Authorization: Bearer $GATEWAY_TOKEN
        </CodeToken>
        {'" \\\n  -d \'{\n    "model": "'}
        <CodeToken tip="Any model any of your pooled providers serves. Omit it and Keypool picks from whatever's active.">
          gemini-2.0-flash
        </CodeToken>
        {'",\n    "messages": [{ "role": "user", "content": "hi" }]\n  }\''}
      </pre>
    </div>
  );
}

const LIVE_FEED_SAMPLE = [
  { provider: "gemini", color: "#4F8EF7", model: "gemini-2.0-flash", ms: 412, status: "ok" },
  { provider: "groq", color: "#F97316", model: "llama-3.3-70b", ms: 189, status: "ok" },
  { provider: "gemini", color: "#4F8EF7", model: "gemini-2.0-flash", ms: 3, status: "429 → retry" },
  { provider: "openrouter", color: "#A78BFA", model: "claude-3-5-haiku", ms: 731, status: "ok" },
];

export default function LandingPage({ onSignIn }: { onSignIn: () => void }) {
  return (
    <div className="min-h-screen w-full grid-bg text-foreground" style={{ background: "var(--background)" }}>
      <header className="sticky top-0 z-10 backdrop-blur-sm border-b border-border" style={{ background: "rgba(10,10,11,0.8)" }}>
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: "rgba(0,214,143,0.1)" }}>
              <KeyRound size={13} className="text-primary" />
            </div>
            <span className="text-[13px] font-medium tracking-tight">keypool</span>
          </div>
          <button
            onClick={onSignIn}
            className="text-[13px] font-medium px-3.5 py-1.5 rounded-md transition-transform hover:scale-[1.02]"
            style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
          >
            Sign in with Google
          </button>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-16">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div>
            <p className="text-[11px] font-mono uppercase tracking-wider mb-4 text-muted-foreground">
              self-hosted / v0.4
            </p>
            <h1 className="text-[34px] md:text-[42px] leading-[1.1] font-semibold tracking-tight mb-5">
              One endpoint. Many keys.
              <br />
              Zero 429s reaching your app.
            </h1>
            <p className="text-[15px] leading-relaxed mb-8 max-w-md text-muted-foreground">
              Keypool sits between your app and Gemini, Groq, or OpenRouter.
              It holds your keys, rotates them per request, and retries on a
              different key the moment one gets rate limited — same request
              and response shape as the OpenAI API.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={onSignIn}
                className="text-[14px] font-medium px-5 py-2.5 rounded-md flex items-center gap-2 transition-transform hover:scale-[1.02]"
                style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
              >
                Sign in with Google
                <ArrowRight size={15} />
              </button>
              <span className="text-[12px] font-mono text-muted-foreground">
                self-serve, no sales call
              </span>
            </div>
          </div>
          <FailoverChain />
        </div>
      </section>

      {/* Providers */}
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

      {/* Live feed + what it does */}
      <section className="max-w-5xl mx-auto px-6 pb-16">
        <div className="grid md:grid-cols-[1.1fr_0.9fr] gap-8 items-start">
          <div className="rounded-xl overflow-hidden bg-card border border-border">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
              <span className="text-[11px] font-mono text-muted-foreground">live request feed</span>
              <span className="text-[10px] font-mono flex items-center gap-1.5 text-primary">
                <span className="w-1 h-1 rounded-full animate-pulse bg-primary" />
                sse
              </span>
            </div>
            <div className="divide-y divide-border">
              {LIVE_FEED_SAMPLE.map((r, i) => (
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

      {/* Code example */}
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

      <footer className="max-w-5xl mx-auto px-6 py-6 text-[12px] font-mono flex items-center justify-between text-muted-foreground border-t border-border">
        <span>keypool</span>
        <span className="hidden sm:inline">
          each account manages its own keys, tokens, and request history
        </span>
      </footer>
    </div>
  );
}