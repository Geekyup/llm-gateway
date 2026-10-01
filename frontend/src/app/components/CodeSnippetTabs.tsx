import { useState } from "react";
import { Check, Copy } from "lucide-react";

const AMBER = "var(--warn)";

type Lang = "python" | "node" | "curl" | "fetch";

const LANG_LABELS: Record<Lang, string> = {
  python: "Python",
  node: "Node.js",
  curl: "cURL",
  fetch: "JS fetch",
};

const FILENAMES: Record<Lang, string> = {
  python: "request.py",
  node: "request.js",
  curl: "request.sh",
  fetch: "request.js",
};

function CodeToken({
  children,
  tip,
  align = "left",
}: {
  children: React.ReactNode;
  tip: string;
  align?: "left" | "right";
}) {
  const [show, setShow] = useState(false);
  return (
    <span
      className="relative inline-block underline decoration-dotted cursor-help"
      style={{ color: "var(--ok)", textDecorationColor: "color-mix(in srgb, var(--ink) 35.0%, transparent)" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          className={`absolute bottom-full mb-2 z-20 max-w-[min(280px,80vw)] whitespace-normal px-2.5 py-1.5 rounded-md text-[12px] font-mono normal-case ${
            align === "right" ? "right-0" : "left-0"
          }`}
          style={{ background: "var(--background)", border: "1px solid color-mix(in srgb, var(--ink) 17%, transparent)", color: "var(--ink)", boxShadow: "0 4px 16px rgba(26,26,24,0.24)" }}
        >
          {tip}
        </span>
      )}
    </span>
  );
}

function buildSnippet(lang: Lang, baseUrl: string, token: string): { pre: string; post: string } {
  switch (lang) {
    case "python":
      return {
        pre: `from openai import OpenAI

client = OpenAI(
    base_url="${baseUrl}/v1",
    api_key="`,
        post: `",
)

response = client.chat.completions.create(
    model=None,  # optional — keypool picks one from the pool
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)`,
      };

    case "node":
      return {
        pre: `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${baseUrl}/v1",
  apiKey: "`,
        post: `",
});

const response = await client.chat.completions.create({
  // model is optional — keypool picks one from the pool
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);`,
      };

    case "curl":
      return {
        pre: `curl ${baseUrl}/v1/chat/completions \\
  -H "Authorization: Bearer `,
        post: `" \\
  -H "Content-Type: application/json" \\
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}]
  }'`,
      };

    case "fetch":
      return {
        pre: `const response = await fetch("${baseUrl}/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer `,
        post: `",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    // model is optional — keypool picks one from the pool
    messages: [{ role: "user", content: "Hello!" }],
  }),
});
const data = await response.json();
console.log(data.choices[0].message.content);`,
      };
  }
}

export function CodeSnippetTabs({
  token,
  baseUrl,
}: {
  token: string;
  baseUrl: string;
}) {
  const [active, setActive] = useState<Lang>("python");
  const [copied, setCopied] = useState(false);

  const { pre, post } = buildSnippet(active, baseUrl, token);
  const fullSnippet = pre + token + post;

  function copy() {
    navigator.clipboard.writeText(fullSnippet).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="mt-3 rounded-lg overflow-hidden" style={{ background: "var(--sidebar)", border: "1px solid color-mix(in srgb, var(--ink) 20%, transparent)" }}>
      <div
        className="flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-center"
        style={{ background: "var(--card)", borderBottom: "1px solid color-mix(in srgb, var(--ink) 17%, transparent)" }}
      >
        <div className="flex items-center gap-2 shrink-0">
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: "var(--bad)" }} />
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: AMBER }} />
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: "var(--ok)" }} />
          <span className="text-[12px] font-mono text-ink-3 ml-1">{FILENAMES[active]}</span>
        </div>

        <div className="flex items-center gap-1 overflow-x-auto sm:ml-3 -mx-1 px-1 sm:mx-0 sm:px-0 no-scrollbar">
          {(Object.keys(LANG_LABELS) as Lang[]).map((lang) => (
            <button
              key={lang}
              onClick={() => setActive(lang)}
              className="relative px-2.5 py-1 text-[12px] font-medium rounded-md transition-colors whitespace-nowrap shrink-0"
              style={{ color: active === lang ? "var(--background)" : "var(--ink-2)", background: active === lang ? "var(--ink)" : "color-mix(in srgb, var(--ink) 10%, transparent)" }}
            >
              {LANG_LABELS[lang]}
            </button>
          ))}
        </div>

        <button
          onClick={copy}
          className="flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] font-medium transition-colors shrink-0 sm:ml-auto"
          style={{ background: copied ? "color-mix(in srgb, var(--ok) 15%, transparent)" : "color-mix(in srgb, var(--ink) 14%, transparent)", color: copied ? "var(--ok)" : "var(--ink-2)" }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      <pre className="px-4 py-3.5 text-[12.5px] leading-relaxed font-mono overflow-x-auto whitespace-pre" style={{ color: "var(--ink-2)" }}>
        {pre}
        <CodeToken tip="Your gateway token — keep it secret, it grants access to your whole key pool." align="left">
          {token}
        </CodeToken>
        {post}
      </pre>
    </div>
  );
}