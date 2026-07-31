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
    model=None,  # необязательно — гейтвей сам подберёт ключ из пула
    messages=[{"role": "user", "content": "Привет!"}],
)
print(response.choices[0].message.content)`;

    case "node":
      return `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${baseUrl}/v1",
  apiKey: "${token}",
});

const response = await client.chat.completions.create({
  // model не обязателен — гейтвей сам подберёт ключ из пула
  messages: [{ role: "user", content: "Привет!" }],
});
console.log(response.choices[0].message.content);`;

    case "curl":
      return `curl ${baseUrl}/v1/chat/completions \\
  -H "Authorization: Bearer ${token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "messages": [{"role": "user", "content": "Привет!"}]
  }'`;

    case "fetch":
      return `const response = await fetch("${baseUrl}/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer ${token}",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    // model не обязателен — гейтвей сам подберёт ключ из пула
    messages: [{ role: "user", content: "Привет!" }],
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
    <div className="mt-3">
      <div className="flex items-center gap-1 mb-2">
        {(Object.keys(LANG_LABELS) as Lang[]).map((lang) => (
          <button
            key={lang}
            onClick={() => setActive(lang)}
            className="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors"
            style={
              active === lang
                ? { background: "rgba(0,214,143,0.12)", color: "#00D68F", border: "1px solid rgba(0,214,143,0.3)" }
                : { background: "transparent", color: "#71717A", border: "1px solid transparent" }
            }
          >
            {LANG_LABELS[lang]}
          </button>
        ))}
      </div>

      <div className="relative rounded-lg" style={{ background: "#0A0A0B", border: "1px solid rgba(255,255,255,0.08)" }}>
        <button
          onClick={copy}
          className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-colors"
          style={{ background: "rgba(255,255,255,0.06)", color: copied ? "#00D68F" : "#ECECF0" }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "Скопировано" : "Copy"}
        </button>
        <pre className="px-3 py-3 pr-20 text-xs font-mono overflow-x-auto whitespace-pre" style={{ color: "#D4D4D8" }}>
          {snippet}
        </pre>
      </div>
    </div>
  );
}