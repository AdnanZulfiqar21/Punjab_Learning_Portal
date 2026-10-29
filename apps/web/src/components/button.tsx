// DESIGN-01: pill buttons. Primary is the dark text colour with the page colour on it (light and dark themes invert
// together); secondary is glass; ghost is text only. md is 44 px tall and lg 48 px, both at least the 44 px touch size.
import Link, { type LinkProps } from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from "react";

/** A Next link's props without its key (taking Link's own props type pulls in a second copy of React's types). */
export type LinkLikeProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { href: LinkProps["href"]; prefetch?: LinkProps["prefetch"]; replace?: boolean; scroll?: boolean };

export type ButtonVariant = "primary" | "secondary" | "ghost";
export type ButtonSize = "md" | "lg";

const BASE =
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-full font-semibold whitespace-nowrap transition duration-200 disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50";
const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-foreground text-background shadow-glass hover:opacity-90",
  secondary: "glass text-foreground hover:border-accent hover:text-accent",
  ghost: "text-foreground hover:bg-surface-muted",
};
const SIZES: Record<ButtonSize, string> = {
  md: "min-h-11 px-5 text-sm",
  lg: "min-h-12 px-6 text-base",
};

/** The class list of a button, for elements that are neither a <button> nor a link (a form's submit, for example). */
export function buttonClasses({ variant = "primary", size = "md", className = "" }: { variant?: ButtonVariant; size?: ButtonSize; className?: string } = {}) {
  return `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`.trim();
}

type Styling = { variant?: ButtonVariant; size?: ButtonSize };

export function Button({ variant, size, className, type = "button", ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & Styling) {
  return <button type={type} className={buttonClasses({ variant, size, className })} {...rest} />;
}

export function ButtonLink({ variant, size, className, ...rest }: LinkLikeProps & Styling) {
  return <Link className={buttonClasses({ variant, size, className })} {...rest} />;
}
