import type { HTMLAttributes, ReactNode } from "react";
import { Check, Copy } from "lucide-react";
import { useCopyToClipboard } from "../../lib/useCopyToClipboard";

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
  const { copied, copy } = useCopyToClipboard();
  const lang = extractLang(className);
  const text = extractText(children).replace(/\n$/, "");

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-block-lang">{lang || "text"}</span>
        <button onClick={() => copy(text)} className="code-block-copy" type="button">
          {copied ? <Check size={12} color="var(--ok)" /> : <Copy size={12} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}