// DESIGN-01 (draft C · Soft Glass), Practice pages: the pieces the Practice group shares. The class and subject pill
// filter, the form-control classes (44 px targets, visible labels), and a few extra Lucide line icons the Practice
// pages need beyond `icons.tsx`.
//
// Icon paths are from Lucide (https://lucide.dev), ISC licence: Copyright (c) for portions of Lucide are held by Cole
// Bemis 2013-2022 as part of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.
// Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby
// granted, provided that the above copyright notice and this permission notice appear in all copies.
import Link from "next/link";
import type { ReactNode, SVGProps } from "react";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { filterHref } from "@/lib/practice-filters";
import { Icon, subjectIconName } from "./icons";

/** A text, number, date or select control: at least 44 px tall, inner radius, solid surface. */
export const FIELD = "min-h-11 rounded-inner border border-border bg-surface px-3.5 py-2 text-foreground";

/** A radio or checkbox shown as a pill; it turns accent when its input is checked. */
export const CHOICE_PILL =
  "flex min-h-11 cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm transition duration-200 hover:border-accent has-checked:border-accent has-checked:bg-accent-soft has-checked:font-semibold has-checked:text-accent";

/** A glass pill button for small secondary actions (Save note, Show). At least 44 px. */
export const SMALL_PILL =
  "glass inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-4 text-sm font-semibold text-foreground shadow-none transition duration-200 hover:border-accent hover:text-accent disabled:pointer-events-none disabled:opacity-50";

/**
 * The class and subject filter of a Practice page: one row per class, the subjects as pills in their own accent. The
 * chosen pill carries `aria-current="page"`; each link's name is "Class 11 Biology".
 */
export function ClassSubjectFilter({ path, grade, subject, subjects }: { path: string; grade: number; subject: string; subjects: [string, string][] }) {
  return (
    <nav aria-label="Choose class and subject" className="glass rounded-card px-4 py-3 sm:px-5">
      <div className="divide-y divide-border/60">
        {[11, 12].map((g) => (
          <div key={g} className="flex flex-col gap-2 py-2.5 sm:flex-row sm:items-center sm:gap-4">
            <span aria-hidden="true" className="w-20 shrink-0 text-xs font-semibold tracking-[0.15em] text-muted uppercase">
              {GRADE_LABEL[g]}
            </span>
            <ul className="flex flex-wrap gap-2">
              {subjects.map(([code, label]) => {
                const active = g === grade && code === subject;
                return (
                  <li key={code} data-subject={subjectKey(code)}>
                    <Link
                      href={filterHref(path, g, code)}
                      aria-current={active ? "page" : undefined}
                      className={`inline-flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm transition duration-200 ${
                        active
                          ? "border-accent bg-accent-soft font-semibold text-accent shadow-glass"
                          : "border-border bg-surface/70 text-foreground hover:border-accent hover:text-accent"
                      }`}
                    >
                      <Icon name={subjectIconName(code)} size={16} className="text-accent" />
                      <span className="sr-only">{GRADE_LABEL[g]} </span>
                      {label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}

const PATHS = {
  "pen-line": ["M12 20h9", "M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z"],
  timer: ["M10 2h4", "m12 14 3-3", "M12 22a8 8 0 1 0 0-16 8 8 0 0 0 0 16z"],
  bookmark: ["m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"],
  "trending-up": ["M16 7h6v6", "m22 7-8.5 8.5-5-5L2 17"],
  "circle-check": ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "m9 12 2 2 4-4"],
  calendar: ["M8 2v4", "M16 2v4", "M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z", "M3 10h18"],
  upload: ["M12 3v12", "m17 8-5-5-5 5", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"],
  printer: [
    "M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2",
    "M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6",
    "M7 14h10a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1z",
  ],
} as const satisfies Record<string, readonly string[]>;

export type PracticeIconName = keyof typeof PATHS;

/** A decorative Lucide line icon in the current text colour (hidden from screen readers). */
export function PracticeIcon({ name, size = 20, strokeWidth = 1.8, ...rest }: Omit<SVGProps<SVGSVGElement>, "children"> & { name: PracticeIconName; size?: number }) {
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
      aria-hidden="true"
      {...rest}
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

/** The 46 px rounded accent tile with an icon, as a subject tile has (decorative). */
export function IconTile({ children, size = 46 }: { children: ReactNode; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="inline-grid shrink-0 place-items-center rounded-[14px] bg-accent text-white dark:text-background"
      style={{ width: size, height: size, boxShadow: "0 6px 16px color-mix(in srgb, var(--accent) 40%, transparent)" }}
    >
      {children}
    </span>
  );
}
