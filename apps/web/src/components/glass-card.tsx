// DESIGN-01: the glass card (radius 24, padding 22 px). Interactive cards lift 2 px with a stronger shadow and the
// accent border on hover and keyboard focus. Never put lesson text in one (owner rule 5: lessons stay on solid).
import Link from "next/link";
import type { HTMLAttributes } from "react";
import type { LinkLikeProps } from "./button";

const BASE = "glass rounded-card";
const PAD = "p-[22px]";
export const INTERACTIVE =
  "transition duration-200 hover:-translate-y-0.5 hover:border-accent hover:shadow-[var(--shadow-glass-hover)] focus-visible:-translate-y-0.5 focus-visible:border-accent motion-reduce:hover:translate-y-0 motion-reduce:focus-visible:translate-y-0";

type CardTag = "div" | "section" | "article" | "li" | "aside";

export type GlassCardProps = HTMLAttributes<HTMLElement> & {
  /** The element to render (default div). Use section with aria-labelledby for a titled region. */
  as?: CardTag;
  /** Hover/focus lift for a card that contains its own link or button (use GlassCardLink when the whole card links). */
  interactive?: boolean;
  /** Default padding 22 px; false for cards that lay out their own (lists with dividers). */
  padded?: boolean;
};

export function GlassCard({ as: Tag = "div", interactive = false, padded = true, className = "", ...rest }: GlassCardProps) {
  const cls = `${BASE} ${padded ? PAD : ""} ${interactive ? `${INTERACTIVE} focus-within:border-accent` : ""} ${className}`;
  return <Tag className={cls.replace(/\s+/g, " ").trim()} {...rest} />;
}

/** A whole card that is one link, with the interactive lift. */
export function GlassCardLink({ className = "", padded = true, ...rest }: LinkLikeProps & { padded?: boolean }) {
  const display = /(^|\s)(flex|grid|inline-flex|inline-grid|block)(\s|$)/.test(className) ? "" : "block";
  return <Link className={`${BASE} ${padded ? PAD : ""} ${INTERACTIVE} ${display} ${className}`.replace(/\s+/g, " ").trim()} {...rest} />;
}
