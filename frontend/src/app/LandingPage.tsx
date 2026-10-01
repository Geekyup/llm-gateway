import { useEffect, useRef, useState } from "react";
import { ArrowRight, Github } from "lucide-react";
import { StatusBadge } from "./components/shared/StatusBadge";
import { UsageBar } from "./components/shared/UsageBar";
import { pingMeta, providerMeta } from "./lib/domain";
import type { Status } from "./types";

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
    <div className="border-y border-border">
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
          className={`absolute bottom-full mb-2 z-30 w-[240px] max-w-[80vw] whitespace-normal px-2.5 py-1.5 text-[12px] font-mono normal-case bg-card border border-border text-ink ${
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

type PreviewRow = {
  name: string;
  provider: string;
  status: Status;
  used: number;
  limit: number;
  ping: number;
  lastUsed: string;
  cooldown?: number;
};

const PREVIEW_ROWS: PreviewRow[] = [
  { name: "key_01", provider: "gemini", status: "active", used: 412, limit: 1500, ping: 142, lastUsed: "4s ago" },
  { name: "key_02", provider: "gemini", status: "cooldown", used: 1498, limit: 1500, ping: 611, lastUsed: "1m ago", cooldown: 252 },
  { name: "key_03", provider: "groq", status: "active", used: 2210, limit: 14400, ping: 96, lastUsed: "9s ago" },
  { name: "key_04", provider: "openrouter", status: "active", used: 38, limit: 200, ping: 388, lastUsed: "31s ago" },
  { name: "key_05", provider: "groq", status: "exhausted", used: 14400, limit: 14400, ping: 1240, lastUsed: "2h ago" },
];

function formatCountdown(total: number) {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function DashboardPreview() {
  const [left, setLeft] = useState(252);

  useEffect(() => {
    const id = setInterval(() => setLeft((v) => (v <= 1 ? 252 : v - 1)), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="border border-border bg-card">
      <div className="flex items-center justify-between px-4 h-11 border-b border-border">
        <span className="text-[13px] text-ink-2">Dashboard / Keys</span>
        <span className="font-mono text-[12px] text-ink-3">5 keys · 3 active</span>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[720px]">
          <div className="grid grid-cols-[1.1fr_1fr_1.2fr_1.6fr_0.7fr_0.8fr] gap-4 px-4 py-2.5 border-b border-border text-[12px] text-ink-3">
            <span>Key</span>
            <span>Provider</span>
            <span>Status</span>
            <span>Usage today</span>
            <span>Ping</span>
            <span>Last used</span>
          </div>
          {PREVIEW_ROWS.map((r) => {
            const meta = providerMeta(r.provider);
            const ping = pingMeta(r.ping);
            return (
              <div
                key={r.name}
                className="grid grid-cols-[1.1fr_1fr_1.2fr_1.6fr_0.7fr_0.8fr] gap-4 px-4 py-3.5 items-center border-b border-border last:border-b-0"
              >
                <span className="font-mono text-[13px] text-ink">{r.name}</span>
                <span className="inline-flex items-center gap-2 text-[13px] text-ink-2">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: meta.color }} />
                  {meta.name}
                </span>
                <StatusBadge status={r.status} cooldownText={r.cooldown ? formatCountdown(left) : undefined} />
                <UsageBar used={r.used} limit={r.limit} status={r.status} />
                <span className="font-mono text-[13px]" style={{ color: ping.color }}>
                  {ping.text}
                </span>
                <span className="font-mono text-[13px] text-ink-3">{r.lastUsed}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const STEPS = [
  {
    n: "01",
    title: "Add keys",
    body: "Paste every Gemini, Groq and OpenRouter key you own. Set a daily cap per key, or pin a key to one model.",
  },
  {
    n: "02",
    title: "Point your client at one URL",
    body: "Same /v1/chat/completions body and response fields as the OpenAI API. Change the base URL and the token.",
  },
  {
    n: "03",
    title: "Stop handling 429s",
    body: "A rate-limited key goes into cooldown and the same request retries on the next one. Your app sees a normal response.",
  },
];

const FEATURES = [
  { title: "Failover on 429", body: "A rate-limited or exhausted key is skipped. The request retries on the next available key, streaming included." },
  { title: "Per-key limits", body: "Daily caps per key and optional pinning of a key to a specific model." },
  { title: "Ping and health checks", body: "Latency for every key at a glance, plus a one-click check for the whole pool." },
  { title: "Gateway tokens", body: "Separate revocable tokens for your API. Google sign-in is only for the dashboard." },
  { title: "Live activity", body: "Request feed over SSE, usage and token charts per key, and a chat playground to test a key." },
  { title: "Runs itself", body: "A background worker lifts cooldowns and resets daily limits. Provider keys are encrypted at rest." },
];

export default function LandingPage({ onSignIn }: { onSignIn: () => void }) {
  return (
    <div className="min-h-screen w-full bg-background text-foreground">
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <span className="font-mono font-medium text-[18px]">
            key<span style={{ color: "var(--accent)" }}>pool</span>
          </span>
          <nav className="flex items-center gap-5">
            <a href="#preview" className="hidden md:inline text-[13px] text-ink-3 hover:text-ink transition-colors">
              Dashboard
            </a>
            <a href="#features" className="hidden md:inline text-[13px] text-ink-3 hover:text-ink transition-colors">
              Features
            </a>
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
          </nav>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-6 pt-16 md:pt-24 pb-16 md:pb-20">
        <div className="grid md:grid-cols-12 gap-12 md:gap-10 items-center">
          <div className="md:col-span-7">
            <p className="font-mono text-[13px] text-ink-3 mb-6">self-hosted LLM key pool</p>
            <h1
              className="font-display text-ink"
              style={{ fontSize: "clamp(38px, 5.6vw, 68px)", lineHeight: 1.05, letterSpacing: "-0.035em", fontWeight: 600 }}
            >
              Keys run out.
              <br />
              <span style={{ color: "var(--accent)" }}>Requests shouldn’t fail.</span>
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
            <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px] text-ink-3">
              {["gemini", "groq", "openrouter"].map((k) => {
                const m = providerMeta(k);
                return (
                  <span key={k} className="inline-flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: m.color }} />
                    {m.name}
                  </span>
                );
              })}
              <span className="text-ink-4">OpenAI-compatible</span>
            </div>
          </div>
          <div className="md:col-span-5">
            <PoolLedger />
          </div>
        </div>
      </section>

      <section id="preview" className="border-t border-border bg-sidebar">
        <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
          <div className="max-w-2xl mb-10">
            <h2 className="font-display text-[28px] md:text-[36px] leading-[1.12]" style={{ fontWeight: 600, letterSpacing: "-0.03em" }}>
              See what every key is doing.
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-2">
              Status, daily usage, latency and last activity for each key in one table. A key in cooldown counts down on its own.
            </p>
          </div>
          <DashboardPreview />
        </div>
      </section>

      <section className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
          <h2 className="font-display text-[28px] md:text-[36px] leading-[1.12] mb-12" style={{ fontWeight: 600, letterSpacing: "-0.03em" }}>
            Three steps, no SDK.
          </h2>
          <ol className="grid md:grid-cols-3 gap-x-10 gap-y-10">
            {STEPS.map((s) => (
              <li key={s.n} className="border-t border-border pt-4">
                <span className="font-mono text-[13px]" style={{ color: "var(--accent)" }}>
                  {s.n}
                </span>
                <h3 className="mt-3 mb-2 text-[17px] font-medium text-ink">{s.title}</h3>
                <p className="text-[15px] leading-relaxed text-ink-2">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="features" className="border-t border-border bg-sidebar">
        <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
          <h2 className="font-display text-[28px] md:text-[36px] leading-[1.12] mb-12" style={{ fontWeight: 600, letterSpacing: "-0.03em" }}>
            What it does.
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 border-t border-l border-border">
            {FEATURES.map((f) => (
              <div key={f.title} className="p-6 border-r border-b border-border">
                <h3 className="text-[16px] font-medium text-ink mb-2">{f.title}</h3>
                <p className="text-[14px] leading-relaxed text-ink-2">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-16 md:py-20 grid md:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="font-display text-[28px] md:text-[36px] leading-[1.12] mb-5" style={{ fontWeight: 600, letterSpacing: "-0.03em" }}>
              The request you already write.
            </h2>
            <p className="text-[15px] leading-relaxed text-ink-2 max-w-md">
              Point your existing OpenAI client at the gateway URL with a gateway token. Nothing else in your integration changes.
            </p>
          </div>
          <RequestSnippet />
        </div>
      </section>

      <section className="border-t border-border bg-sidebar">
        <div className="max-w-6xl mx-auto px-6 py-16 md:py-20 flex flex-col md:flex-row md:items-center md:justify-between gap-8">
          <div>
            <h2 className="font-display text-[28px] md:text-[36px] leading-[1.12]" style={{ fontWeight: 600, letterSpacing: "-0.03em" }}>
              Add your keys. Keep your code.
            </h2>
            <p className="mt-4 font-mono text-[13px] text-ink-3">self-host: docker compose up --build</p>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
            <SignInButton onClick={onSignIn} showArrow />
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="text-[14px] text-ink underline underline-offset-4 decoration-ink-4 hover:decoration-ink"
            >
              Source on GitHub
            </a>
          </div>
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
