import { useState } from "react";
import { Check, Copy, RotateCcw } from "lucide-react";

export function MessageActions({
  content,
  onRegenerate,
  className,
}: {
  content: string;
  onRegenerate?: () => void;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // clipboard unavailable — ignore
    }
  }

  return (
    <div className={`message-actions ${className ?? ""}`}>
      <button onClick={copy} title="Copy" type="button" className="message-action-btn">
        {copied ? <Check size={12} color="#00D68F" /> : <Copy size={12} />}
      </button>
      {onRegenerate && (
        <button onClick={onRegenerate} title="Regenerate" type="button" className="message-action-btn">
          <RotateCcw size={12} />
        </button>
      )}
    </div>
  );
}