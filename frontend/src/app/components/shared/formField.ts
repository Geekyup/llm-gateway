import type { CSSProperties, FocusEvent } from "react";

export const FIELD_BORDER = "color-mix(in srgb, var(--ink) 10.2%, transparent)";
export const FOCUS_BORDER = "color-mix(in srgb, var(--accent) 40%, transparent)";
export const FIELD_SHADOW = "inset 0 1px 0 rgba(0,0,0,0.3)";
const FOCUS_SHADOW = `${FIELD_SHADOW}, 0 0 0 3px color-mix(in srgb, var(--accent) 7%, transparent)`;

export const FIELD_STYLE: CSSProperties = {
  background: "var(--field)",
  border: `1px solid ${FIELD_BORDER}`,
  boxShadow: FIELD_SHADOW,
  color: "var(--ink)",
};

export function focusField(e: FocusEvent<HTMLElement>) {
  e.currentTarget.style.borderColor = FOCUS_BORDER;
  e.currentTarget.style.boxShadow = FOCUS_SHADOW;
}

export function blurField(e: FocusEvent<HTMLElement>) {
  e.currentTarget.style.borderColor = FIELD_BORDER;
  e.currentTarget.style.boxShadow = FIELD_SHADOW;
}
