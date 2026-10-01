import { KeyRound } from "lucide-react";
import { GoogleGemini, Groq, Openrouter } from "@thesvg/react";
import type { ComponentType, SVGProps } from "react";
import type { Provider } from "../../types";

const ICONS: Record<Provider, ComponentType<SVGProps<SVGSVGElement>>> = {
  gemini: GoogleGemini,
  openrouter: Openrouter,
  groq: Groq,
};

export function ProviderIcon({
  provider,
  size = 14,
  className,
}: {
  provider: string;
  size?: number;
  className?: string;
}) {
  const Icon = ICONS[provider as Provider];
  if (!Icon) return <KeyRound size={size} color="var(--ink-3)" className={className} />;
  return <Icon width={size} height={size} className={className} />;
}