import { useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { startGoogleLogin } from "../../lib/api";

export function LoginGate({ error }: { error?: string | null }) {
  const [googleLoginPending, setGoogleLoginPending] = useState(false);

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: "#0A0A0B", fontFamily: "Inter, sans-serif" }}>
      <div
        className="w-full max-w-sm rounded-2xl p-6"
        style={{ background: "#141416", border: "1px solid rgba(255,255,255,0.09)", boxShadow: "0 32px 80px rgba(0,0,0,0.6)" }}
      >
        <div className="mb-6">
          <p className="font-mono text-sm font-semibold tracking-tight" style={{ letterSpacing: "0.01em" }}>
            <span className="text-zinc-100">key</span>
            <span style={{ color: "#00D68F" }}>pool</span>
          </p>
          <p className="text-[11px] text-zinc-600 mt-1">Sign in to manage your keys</p>
        </div>

        {error && (
          <p className="mb-4 text-xs flex items-center gap-1.5" style={{ color: "#EF4444" }}>
            <AlertTriangle size={12} className="shrink-0" /> {error}
          </p>
        )}

        <button
          onClick={() => { setGoogleLoginPending(true); startGoogleLogin(); }}
          disabled={googleLoginPending}
          className="w-full py-2 rounded-lg text-sm font-semibold transition-all active:scale-[0.97] disabled:active:scale-100 disabled:opacity-70 flex items-center justify-center gap-2"
          style={{ background: "#00D68F", color: "#0A0A0B" }}
        >
          {googleLoginPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="#0A0A0B"
                d="M12 11v2.8h6.5c-.3 1.6-2.1 4.7-6.5 4.7-3.9 0-7.1-3.2-7.1-7.2s3.2-7.2 7.1-7.2c2.2 0 3.7.9 4.6 1.7l3.1-3C17.6 1 15.1 0 12 0 5.4 0 0 5.4 0 12s5.4 12 12 12c6.9 0 11.5-4.8 11.5-11.6 0-.8-.1-1.4-.2-2H12z"
              />
            </svg>
          )}
          {googleLoginPending ? "Redirecting..." : "Sign in with Google"}
        </button>

        <p className="mt-4 text-[11px] text-zinc-600 leading-relaxed">
          Each account only sees and manages its own keys, gateway tokens,
          and request history.
        </p>
      </div>
    </div>
  );
}