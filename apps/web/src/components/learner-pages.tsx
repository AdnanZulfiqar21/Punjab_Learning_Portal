// DESIGN-01 (draft C · Soft Glass), learner pages (search, account, sign-in, onboarding, help, pricing, notifications,
// not-found, error): the few pieces those pages share. Line icons beyond components/icons.tsx, the form field and
// choice-pill classes, a section title with an icon tile, and the centred glass card for the sign-in style pages.
// Icon paths are from Lucide (ISC licence; Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as
// part of Feather (MIT); all other copyright (c) for Lucide are held by Lucide Contributors 2022), as in icons.tsx.
import type { ReactNode, SVGProps } from "react";

const PATHS = {
  user: ["M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2", "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"],
  bell: ["M10.268 21a2 2 0 0 0 3.464 0", "M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"],
  "log-out": ["m16 17 5-5-5-5", "M21 12H9", "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"],
  "circle-help": ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3", "M12 17h.01"],
  lock: ["M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z", "M7 11V7a5 5 0 0 1 10 0v4"],
  download: ["M12 15V3", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "m7 10 5 5 5-5"],
  "credit-card": ["M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z", "M2 10h20"],
  smartphone: ["M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z", "M12 18h.01"],
  monitor: ["M4 3h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z", "M8 21h8", "M12 17v4"],
  shield: [
    "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
  ],
  eye: ["M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0", "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"],
  check: ["M20 6 9 17l-5-5"],
  "triangle-alert": ["m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3", "M12 9v4", "M12 17h.01"],
  "rotate-cw": ["M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8", "M21 3v5h-5"],
  "message-circle": ["M7.9 20A9 9 0 1 0 4 16.1L2 22z"],
  plus: ["M5 12h14", "M12 5v14"],
  "graduation-cap": [
    "M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z",
    "M22 10v6",
    "M6 12.5V16a6 3 0 0 0 12 0v-3.5",
  ],
  compass: ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z"],
  "arrow-left": ["m12 19-7-7 7-7", "M19 12H5"],
  "chevron-down": ["m6 9 6 6 6-6"],
  funnel: [
    "M10 20a1 1 0 0 0 .553.895l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .517-1.341L21.74 4.67A1 1 0 0 0 21 3H3a1 1 0 0 0-.742 1.67l7.225 7.989A2 2 0 0 1 10 14z",
  ],
  send: [
    "M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z",
    "m21.854 2.147-10.94 10.939",
  ],
  "sliders-horizontal": ["M10 5H3", "M12 19H3", "M14 3v4", "M16 17v4", "M21 12h-9", "M21 19h-5", "M21 5h-7", "M8 10v4", "M8 12H3"],
  "file-text": ["M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z", "M14 2v4a2 2 0 0 0 2 2h4", "M16 13H8", "M16 17H8", "M10 9H8"],
} as const satisfies Record<string, readonly string[]>;

export type PageIconName = keyof typeof PATHS;

/** A Lucide line icon in the current text colour; decorative (hidden from screen readers) unless it has a label. */
export function PageIcon({
  name,
  size = 20,
  label,
  strokeWidth = 1.8,
  ...rest
}: Omit<SVGProps<SVGSVGElement>, "children"> & { name: PageIconName; size?: number; label?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
      {...rest}
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

/** A text input, select or textarea: solid surface (what is typed is read, not looked through), 44 px tall. */
export const FIELD =
  "w-full min-h-11 rounded-inner border border-border bg-surface px-4 py-2.5 text-foreground transition duration-200 hover:border-accent/60 focus-visible:border-accent";

/** A radio or checkbox shown as a pill: the whole pill is the label, the checked one takes the accent. */
export const CHOICE_PILL =
  "flex min-h-11 cursor-pointer items-center gap-2.5 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium transition duration-200 hover:border-accent has-[:checked]:border-accent has-[:checked]:bg-accent-soft [&>input]:size-4 [&>input]:accent-[var(--accent)]";

/** A field's visible label. */
export const LABEL = "block text-sm font-semibold";

/** A rounded tile with an icon in the accent, beside a card's title. Decorative. */
export function IconTile({ icon, tone = "accent", size = 40 }: { icon: PageIconName; tone?: "accent" | "danger"; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-grid shrink-0 place-items-center rounded-[12px] ${tone === "danger" ? "bg-danger-soft text-danger" : "bg-accent-soft text-accent"}`}
      style={{ width: size, height: size }}
    >
      <PageIcon name={icon} size={Math.round(size * 0.5)} />
    </span>
  );
}

/** A card section's heading row: icon tile, the heading (h2 by default) and an optional action at the end. */
export function CardTitle({ id, icon, children, action, level = 2 }: { id?: string; icon: PageIconName; children: ReactNode; action?: ReactNode; level?: 2 | 3 }) {
  const H = level === 2 ? "h2" : "h3";
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-3">
        <IconTile icon={icon} />
        <H id={id} className="min-w-0 font-display text-lg font-semibold tracking-tight break-words">
          {children}
        </H>
      </div>
      {action && <div className="text-sm">{action}</div>}
    </div>
  );
}

/** The centred glass card over the mesh (sign in, set up, not found, errors): icon, h1, lead, then the content. */
export function CenteredCard({
  icon,
  tone = "accent",
  title,
  lead,
  children,
  width = "md",
  role,
}: {
  icon: PageIconName;
  tone?: "accent" | "danger";
  title: ReactNode;
  lead?: ReactNode;
  children?: ReactNode;
  width?: "md" | "2xl";
  role?: "alert";
}) {
  return (
    <div className={`mx-auto pt-6 sm:pt-12 ${width === "md" ? "max-w-md" : "max-w-2xl"}`}>
      <div role={role} className="glass space-y-6 rounded-card px-5 py-7 sm:px-9 sm:py-10">
        <div className="space-y-3 text-center">
          <span className="inline-flex">
            <IconTile icon={icon} tone={tone} size={52} />
          </span>
          <h1 className="font-display text-[28px] leading-9 font-bold tracking-tight sm:text-[32px] sm:leading-10">{title}</h1>
          {lead && <p className="mx-auto max-w-prose text-muted">{lead}</p>}
        </div>
        {children}
      </div>
    </div>
  );
}
