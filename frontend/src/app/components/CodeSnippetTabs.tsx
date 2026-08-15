import { useState } from "react";
import { Check, Copy } from "lucide-react";

type Lang = "python" | "node" | "curl" | "fetch";

const LANG_LABELS: Record<Lang, string> = {
  python: "Python",
  node: "Node.js",
  curl: "cURL",
  fetch: "JS fetch",
};

function buildSnippet(lang: Lang, baseUrl: string, token: string): string {
  switch (lang) {
    case "python":
      return `from openai import OpenAI

client = OpenAI(
    base_url="${baseUrl}/v1",
    api_key="${token}",
)

response = client.chat.completions.create(
    model=None,  # optional — keypool picks one from the pool
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)`;

    case "node":
      return `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${baseUrl}/v1",
  apiKey: "${token}",
});

const response = await client.chat.completions.create({
  // model is optional — keypool picks one from the pool
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);`;

    case "curl":
      return `curl ${baseUrl}/v1/chat/completions \\
  -H "Authorization: Bearer ${token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}]
  }'`;

    case "fetch":
      return `const response = await fetch("${baseUrl}/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer ${token}",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    // model is optional — keypool picks one from the pool
    messages: [{ role: "user", content: "Hello!" }],
  }),
});
const data = await response.json();
console.log(data.choices[0].message.content);`;
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

  const snippet = buildSnippet(active, baseUrl, token);

  function copy() {
    navigator.clipboard.writeText(snippet).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="mt-3 rounded-xl overflow-hidden" style={{ background: "#0A0A0B", border: "1px solid rgba(255,255,255,0.08)" }}>
      <div
        className="flex items-center justify-between pl-1 pr-1.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-0.5">
          {(Object.keys(LANG_LABELS) as Lang[]).map((lang) => (
            <button
              key={lang}
              onClick={() => setActive(lang)}
              className="relative px-3 py-2 text-[12px] font-medium transition-colors"
              style={{ color: active === lang ? "#ECECF0" : "#71717A" }}
            >
              {LANG_LABELS[lang]}
              {active === lang && (
                <span
                  className="absolute left-2 right-2 bottom-0 h-[2px] rounded-full"
                  style={{ background: "#00D68F" }}
                />
              )}
            </button>
          ))}
        </div>
        <button
          onClick={copy}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-colors shrink-0"
          style={{ background: copied ? "rgba(0,214,143,0.1)" : "rgba(255,255,255,0.05)", color: copied ? "#00D68F" : "#A1A1AA" }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      <pre className="px-4 py-3.5 text-[12.5px] leading-relaxed font-mono overflow-x-auto whitespace-pre" style={{ color: "#D4D4D8" }}>
        {snippet}
      </pre>
    </div>
  );
}