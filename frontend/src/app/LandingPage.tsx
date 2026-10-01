import { useEffect, useRef, useState } from "react";
import { ArrowRight, Github } from "lucide-react";

const REPO_URL = "https://github.com/Geekyup/llm-gateway";

type PoolKey = { name: string; provider: string; fill: number };

const POOL: PoolKey[] = [
  { name: "key_01", provider: "gemini", fill: 11 },
  { name: "key_02", provider: "gemini", fill: 14 },
  { name: "key_03", provider: "groq", fill: 6 },
  { name: "key_04", provider: "openrouter", fill: 9 },
  { name: "key_05", provider: "groq", fill: 3 },
];

const SLOTS = 16;

function PoolLedger() {
  const [active, setActive] = useState(0);
  const [limited, setLimited] = useState<number | null>(null);
  const [cooling, setCooling] = useState<Set<number>>(new Set());
  const activeRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

    async function cycle() {
      while (!cancelled) {
        await sleep(2400);
        if (cancelled) return;
        const current = activeRef.current;
        setLimited(current);
        await sleep(700);
        if (cancelled) return;
        const next = (current + 1) % POOL.length;
        setCooling((prev) => new Set(prev).add(current));
        setActive(next);
        activeRef.current = next;
        setLimited(null);
        await sleep(5200);
        if (cancelled) return;
        setCooling((prev) => {
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

  function stateOf(i: number) {
    if (limited === i) return "429";
    if (i === active) return "serving";
    if (cooling.has(i)) return "cooldown";
    return "idle";
  }

  return (
    <div className="border-y-2 border-ink">
      <div className="flex items-baseline justify-between py-2 border-b border-border">
        <span className="font-mono text-[12px] text-ink-3">pool / 5 keys / 3 providers</span>
        <span className="font-mono text-[12px] text-ink-3">requests today</span>
      </div>
      <ul role="img" aria-label={`Key pool: ${POOL[active].name} is serving requests`}>
        {POOL.map((k, i) => {
          const state = stateOf(i);
          const isActive = state === "serving";
          const isLimited = state === "429";
          const color = isLimited ? "var(--bad)" : state === "cooldown" ? "var(--warn)" : isActive ? "var(--accent)" : "var(--ink-4)";
          return (
            <li
              key={k.name}
              className="grid grid-cols-[18px_64px_1fr_74px] items-center gap-3 py-3 border-b border-border transition-colors duration-200"
              style={{ background: isActive ? "color-mix(in srgb, var(--accent) 6%, transparent)" : "transparent" }}
            >
              <span className="font-mono text-[13px]" style={{ color }}>
                {isActive ? "→" : isLimited ? "×" : ""}
              </span>
              <span className="font-mono text-[13px] text-ink">{k.name}</span>
              <div className="flex gap-[2px] h-[10px]">
                {Array.from({ length: SLOTS }).map((_, s) => (
                  <span
                    key={s}
                    className="flex-1"
                    style={{
                      background:
                        s < k.fill
                          ? state === "cooldown"
                            ? "var(--warn)"
                            : isLimited
                              ? "var(--bad)"
                              : "var(--ink)"
                          : "color-mix(in srgb, var(--ink) 7.2%, transparent)",
                    }}
                  />
                ))}
              </div>
              <span className="font-mono text-[12px] text-right" style={{ color }}>
                {state}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="pt-3 font-mono text-[13px] text-ink-2 min-h-[2.4em]" role="status" aria-live="polite">
        {limited !== null ? (
          <>
            <span style={{ color: "var(--bad)" }}>{POOL[limited].name}</span> returned 429. Retrying the same request on{" "}
            {POOL[(limited + 1) % POOL.length].name}.
          </>
        ) : (
          <>
            POST /v1/chat/completions → <span style={{ color: "var(--accent)" }}>{POOL[active].name}</span> ({POOL[active].provider})
          </>
        )}
      </p>
    </div>
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
      className="relative inline-block underline decoration-dotted cursor-help"
      style={{ color: accent ? "var(--accent-hover)" : "inherit", textDecorationColor: "var(--ink-4)" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
      tabIndex={0}
    >
      {children}
      {show && (
        <span
          className={`absolute bottom-full mb-2 z-30 w-[240px] max-w-[80vw] whitespace-normal px-2.5 py-1.5 text-[12px] font-mono normal-case bg-card border border-ink text-ink ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          {tip}
        </span>
      )}
    </span>
  );
}

function RequestSnippet() {
  return (
    <div className="bg-card border border-border text-ink">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <span className="font-mono text-[12px] text-ink-3">request.sh</span>
        <span className="font-mono text-[12px] hidden sm:inline text-ink-4">
          hover the underlined parts
        </span>
      </div>
      <div className="overflow-x-auto">
        <pre className="px-4 pt-10 pb-5 text-[13px] font-mono leading-relaxed w-max min-w-full">
          {"curl https://api.your-gateway.dev/v1/chat/completions \\\n  -H \""}
          <CodeToken tip="Bearer plus a gateway token. Create one under Account → Gateway tokens." accent>
            Authorization: Bearer $GATEWAY_TOKEN
          </CodeToken>
          {'" \\\n  -d \'{\n    "model": "'}
          <CodeToken tip="Any model served by one of your pooled providers. Omit it and the gateway picks from active keys." align="right">
            gemini-2.0-flash
          </CodeToken>
          {'",\n    "messages": [{ "role": "user", "content": "hi" }]\n  }\''}
        </pre>
      </div>
    </div>
  );
}

type FeedRow = { provider: string; model: string; ms: number; status: string };

const FEED_POOL: FeedRow[] = [
  { provider: "gemini", model: "gemini-2.0-flash", ms: 412, status: "200" },
  { provider: "groq", model: "llama-3.3-70b", ms: 189, status: "200" },
  { provider: "gemini", model: "gemini-2.0-flash", ms: 3, status: "429 → retry" },
  { provider: "openrouter", model: "claude-3-5-haiku", ms: 731, status: "200" },
  { provider: "groq", model: "llama-3.1-8b", ms: 94, status: "200" },
  { provider: "openrouter", model: "gpt-4o-mini", ms: 512, status: "200" },
  { provider: "gemini", model: "gemini-1.5-pro", ms: 288, status: "200" },
];

function useLiveFeed(size = 5, intervalMs = 2800) {
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
  const padding = size === "sm" ? "px-3.5 py-1.5 text-[13px]" : "px-5 py-3 text-[15px]";

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
      className={`group font-medium rounded-[2px] flex items-center gap-2 transition-colors disabled:opacity-70 disabled:cursor-not-allowed hover:brightness-90 ${padding}`}
      style={{ background: "var(--accent)", color: "var(--on-accent)" }}
    >
      {pending ? "Redirecting…" : "Sign in with Google"}
      {showArrow && !pending && <ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-0.5" />}
    </button>
  );
}

const STEPS = [
  {
    n: "1",
    title: "Add keys",
    body: "Paste every Gemini, Groq and OpenRouter key you own. Set a daily cap per key, or pin a key to one model.",
  },
  {
    n: "2",
    title: "Point your client at one URL",
    body: "Same /v1/chat/completions body and response fields as the OpenAI API. Change the base URL and the token.",
  },
  {
    n: "3",
    title: "Stop handling 429s",
    body: "A rate-limited key goes into cooldown and the same request retries on the next one. Your app sees a normal response.",
  },
];

export default function LandingPage({ onSignIn }: { onSignIn: () => void }) {
  const feedRows = useLiveFeed();

  return (
    <div className="min-h-screen w-full bg-background text-foreground">
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <span className="font-mono font-medium text-[18px]">
            key<span style={{ color: "var(--accent)" }}>pool</span>
          </span>
          <div className="flex items-center gap-4">
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer noopener"
              aria-label="View source on GitHub"
              className="flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink transition-colors"
            >
              <Github size={15} />
              <span className="hidden sm:inline">Source</span>
            </a>
            <SignInButton onClick={onSignIn} size="sm" />
          </div>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-6 pt-16 md:pt-24 pb-16 md:pb-24">
        <div className="grid md:grid-cols-12 gap-12 md:gap-10 items-end">
          <div className="md:col-span-7">
            <p className="font-mono text-[13px] text-ink-3 mb-6">self-hosted LLM key pool</p>
            <h1
              className="font-display text-ink"
              style={{ fontSize: "clamp(38px, 5.6vw, 68px)", lineHeight: 1.05, letterSpacing: "-0.035em", fontWeight: 600 }}
            >
              Keys run out.
              <br />
              <span style={{ color: "var(--accent-hover)" }}>Requests shouldn’t fail.</span>
            </h1>
            <p className="mt-8 max-w-xl text-[17px] leading-relaxed text-ink-2">
              Round-robin across your Gemini, Groq and OpenRouter keys. When one hits a rate limit it cools down and the same
              request goes out on the next key. OpenAI-compatible, so you change a base URL and nothing else.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-x-5 gap-y-3">
              <SignInButton onClick={onSignIn} showArrow />
              <a
                href={REPO_URL}
                target="_blank"
                rel="noreferrer noopener"
                className="text-[14px] text-ink underline underline-offset-4 decoration-ink-4 hover:decoration-ink"
              >
                Read the source
              </a>
            </div>
          </div>
          <div className="md:col-span-5">
            <PoolLedger />
          </div>
        </div>
      </section>

      <section className="border-t-2 border-ink">
        <div className="max-w-6xl mx-auto px-6 py-16">
          <h2 className="font-display text-[30px] md:text-[38px] leading-[1.1] mb-12" style={{ fontWeight: 600, letterSpacing: "-0.03em" }}>
            Three steps, no SDK.
          </h2>
          <ol className="grid md:grid-cols-3 gap-x-10 gap-y-10">
            {STEPS.map((s) => (
              <li key={s.n} className="border-t border-ink pt-4">
                <span className="font-mono text-[14px] text-ink-3">0{s.n}</span>
                <h3 className="mt-3 mb-2 text-[17px] font-medium text-ink">{s.title}</h3>
                <p className="text-[15px] leading-relaxed text-ink-2">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-16 grid md:grid-cols-2 gap-12 items-start">
          <div>
            <h2 className="font-display text-[28px] md:text-[34px] leading-[1.15] mb-5" style={{ fontWeight: 600, letterSpacing: "-0.03em" }}>
              The request you already write.
            </h2>
            <p className="text-[15px] leading-relaxed text-ink-2 mb-5 max-w-md">
              Point your existing OpenAI client at the gateway URL with a gateway token. Provider keys are encrypted at rest and
              never leave the server.
            </p>
            <div className="mt-8">
              <p className="font-mono text-[13px] text-ink-3 mb-2">recent requests</p>
              <table className="w-full text-[13px] font-mono border-t-2 border-ink">
                <tbody>
                  {feedRows.map((r, i) => (
                    <tr key={i} className="border-b border-border">
                      <td className="py-2 pr-3 text-ink">{r.provider}</td>
                      <td className="py-2 pr-3 text-ink-3 truncate max-w-[140px]">{r.model}</td>
                      <td className="py-2 pr-3 text-right text-ink-3">{r.ms} ms</td>
                      <td className="py-2 text-right" style={{ color: r.status === "200" ? "var(--ink-3)" : "var(--warn)" }}>
                        {r.status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <RequestSnippet />
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-6 text-[13px] flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between text-ink-3">
          <span className="font-mono">
            key<span style={{ color: "var(--accent)" }}>pool</span>
          </span>
          <span>Each account manages its own keys, tokens and request history.</span>
        </div>
      </footer>
    </div>
  );
}
