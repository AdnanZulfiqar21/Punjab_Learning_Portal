// DESIGN-01 (draft C · Soft Glass): the header's sections and which one a page belongs to. Pure, so it is tested on the
// host (tests/nav.test.ts) and shared by the header's client component.

export type Section = "learn" | "practice" | "search" | "help" | "account";

/** The header's links, in order. Account is the separate sign-in/account link (components/account-nav.tsx). */
export const NAV_ITEMS: readonly { key: Exclude<Section, "account">; href: string; label: string }[] = [
  { key: "learn", href: "/learn", label: "Learn" },
  { key: "practice", href: "/practice", label: "Practice" },
  { key: "search", href: "/search", label: "Search" },
  { key: "help", href: "/help", label: "Help" },
];

// First path segment -> section. Pages not listed (home, pricing, study tools, staff pages) mark nothing.
const BY_SEGMENT: Record<string, Section> = {
  learn: "learn",
  practice: "practice",
  search: "search",
  help: "help",
  account: "account",
  signin: "account",
  notifications: "account",
  onboarding: "account",
};

/** The section a pathname belongs to, matched on whole path segments ("/learning" is not Learn). */
export function activeSection(pathname: string | null | undefined): Section | null {
  if (!pathname) return null;
  const path = pathname.split(/[?#]/, 1)[0];
  const first = path.split("/").find((s) => s.length > 0);
  if (!first) return null;
  return Object.hasOwn(BY_SEGMENT, first) ? BY_SEGMENT[first] : null;
}
