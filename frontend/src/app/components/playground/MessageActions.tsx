import { Check, Copy, RotateCcw } from "lucide-react";
import { useCopyToClipboard } from "../../lib/useCopyToClipboard";

export function MessageActions({
  content,
  onRegenerate,
  className,
}: {
  content: string;
  onRegenerate?: () => void;
  className?: string;
}) {
  const { copied, copy } = useCopyToClipboard(1200);

  return (
    <div className={`message-actions ${className ?? ""}`}>
      <button onClick={() => copy(content)} title="Copy" type="button" className="message-action-btn">
        {copied ? <Check size={12} color="var(--ok)" /> : <Copy size={12} />}
      </button>
      {onRegenerate && (
        <button onClick={onRegenerate} title="Regenerate" type="button" className="message-action-btn">
          <RotateCcw size={12} />
        </button>
      )}
    </div>
  );
}