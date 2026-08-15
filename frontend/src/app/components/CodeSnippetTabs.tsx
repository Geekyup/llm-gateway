import { useState } from "react";
import { Check, Copy } from "lucide-react";

const AMBER = "#F59E0B";

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
      style={{ color: "#00D68F", textDecorationColor: "rgba(255,255,255,0.3)" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          className={`absolute bottom-full mb-2 z-20 max-w-[min(280px,80vw)] whitespace-normal px-2.5 py-1.5 rounded-md text-[11px] font-mono normal-case ${
            align === "right" ? "right-0" : "left-0"
          }`}
          style={{ background: "#0A0A0B", border: "1px solid rgba(255,255,255,0.1)", color: "#ECECF0", boxShadow: "0 4px 16px rgba(0,0,0,0.4)" }}
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
    <div className="mt-3 rounded-xl overflow-hidden" style={{ background: "#18181B", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div
        className="flex items-center gap-2 px-3 py-2.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: "#EF4444" }} />
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: AMBER }} />
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: "#00D68F" }} />
        <span className="text-[11px] font-mono text-zinc-500">{FILENAMES[active]}</span>

        <div className="flex items-center gap-0.5 ml-3">
          {(Object.keys(LANG_LABELS) as Lang[]).map((lang) => (
            <button
              key={lang}
              onClick={() => setActive(lang)}
              className="relative px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors"
              style={{ color: active === lang ? "#ECECF0" : "#71717A", background: active === lang ? "rgba(255,255,255,0.06)" : "transparent" }}
            >
              {LANG_LABELS[lang]}
            </button>
          ))}
        </div>

        <button
          onClick={copy}
          className="ml-auto flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-colors shrink-0"
          style={{ background: copied ? "rgba(0,214,143,0.1)" : "rgba(255,255,255,0.05)", color: copied ? "#00D68F" : "#A1A1AA" }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      <pre className="px-4 py-3.5 text-[12.5px] leading-relaxed font-mono overflow-x-auto whitespace-pre" style={{ color: "#D4D4D8" }}>
        {pre}
        <CodeToken tip="Your gateway token — keep it secret, it grants access to your whole key pool." align="left">
          {token}
        </CodeToken>
        {post}
      </pre>
    </div>
  );
}