import { useState, type HTMLAttributes, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";

function extractText(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node && typeof node === "object" && "props" in node) {
    return extractText((node as { props?: { children?: ReactNode } }).props?.children);
  }
  return "";
}

function extractLang(className?: string): string {
  const match = /language-(\w+)/.exec(className ?? "");
  return match ? match[1] : "";
}

export function CodeBlock({ children, className }: HTMLAttributes<HTMLElement> & { children?: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const lang = extractLang(className);
  const text = extractText(children).replace(/\n$/, "");

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable — ignore
    }
  }

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-block-lang">{lang || "text"}</span>
        <button onClick={copy} className="code-block-copy" type="button">
          {copied ? <Check size={12} color="#00D68F" /> : <Copy size={12} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}