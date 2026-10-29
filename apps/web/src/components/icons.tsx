// DESIGN-01: line icons as inline SVG (never emoji). Paths are from Lucide (https://lucide.dev), ISC licence:
// Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other copyright
// (c) for Lucide are held by Lucide Contributors 2022. Permission to use, copy, modify, and/or distribute this software
// for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission
// notice appear in all copies.
import type { SVGProps } from "react";

const PATHS = {
  "arrow-right": ["M5 12h14", "m12 5 7 7-7 7"],
  "chevron-right": ["m9 18 6-6-6-6"],
  menu: ["M4 6h16", "M4 12h16", "M4 18h16"],
  x: ["M18 6 6 18", "m6 6 12 12"],
  search: ["m21 21-4.34-4.34", "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z"],
  "book-open": [
    "M12 7v14",
    "M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z",
  ],
  languages: ["m5 8 6 6", "m4 14 6-6 2-3", "M2 5h12", "M7 2h1", "m22 22-5-10-5 10", "M14 18h6"],
  play: ["M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"],
  "list-checks": ["m3 17 2 2 4-4", "m3 7 2 2 4-4", "M13 6h8", "M13 12h8", "M13 18h8"],
  "file-text": [
    "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z",
    "M14 2v4a2 2 0 0 0 2 2h4",
    "M10 9H8",
    "M16 13H8",
    "M16 17H8",
  ],
  layers: [
    "M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z",
    "M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12",
    "M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17",
  ],
  image: ["M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z", "M9 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z", "m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"],
  // Subjects
  dna: [
    "m10 16 1.5 1.5",
    "m14 8-1.5-1.5",
    "M15 2c-1.798 1.998-2.518 3.995-2.807 5.993",
    "m16.5 10.5 1 1",
    "m17 6-2.891-2.891",
    "M2 15c6.667-6 13.333 0 20-6",
    "m20 9 .891.891",
    "M3.109 14.109 4 15",
    "m6.5 12.5 1 1",
    "m7 18 2.891 2.891",
    "M9 22c1.798-1.998 2.518-3.995 2.807-5.993",
  ],
  "flask-conical": [
    "M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2",
    "M6.453 15h11.094",
    "M8.5 2h7",
  ],
  atom: [
    "M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
    "M20.2 20.2c2.04-2.03.02-7.36-4.5-11.9-4.54-4.52-9.87-6.54-11.9-4.5-2.04 2.03-.02 7.36 4.5 11.9 4.54 4.52 9.87 6.54 11.9 4.5Z",
    "M15.7 15.7c4.52-4.54 6.54-9.87 4.5-11.9-2.03-2.04-7.36-.02-11.9 4.5-4.52 4.54-6.54 9.87-4.5 11.9 2.03 2.04 7.36.02 11.9-4.5Z",
  ],
  code: ["m16 18 6-6-6-6", "m8 6-6 6 6 6"],
  sigma: ["M18 7V5a1 1 0 0 0-1-1H6.5a.5.5 0 0 0-.4.8l4.5 6a2 2 0 0 1 0 2.4l-4.5 6a.5.5 0 0 0 .4.8H17a1 1 0 0 0 1-1v-2"],
} as const satisfies Record<string, readonly string[]>;

export type IconName = keyof typeof PATHS;

type IconProps = Omit<SVGProps<SVGSVGElement>, "children"> & {
  name: IconName;
  /** Pixel size of the square icon (default 20). */
  size?: number;
  /** A label makes the icon meaningful (role="img"); without one it is decorative and hidden from screen readers. */
  label?: string;
};

/** A Lucide line icon in the current text colour. */
export function Icon({ name, size = 20, label, strokeWidth = 1.8, ...rest }: IconProps) {
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

const SUBJECT_ICON: Record<string, IconName> = {
  biology: "dna",
  chemistry: "flask-conical",
  physics: "atom",
  computer_science: "code",
  mathematics: "sigma",
};

/** The icon for a subject code ("biology", "computer_science"); a book for anything else. */
export function subjectIconName(subject: string | null | undefined): IconName {
  return SUBJECT_ICON[(subject ?? "").trim().toLowerCase().replace(/\s+/g, "_")] ?? "book-open";
}

/**
 * A subject's identity tile: a rounded square in the subject accent with its icon and a soft accent glow. Put it
 * inside an element with `data-subject` so `--accent` is that subject's colour. Decorative; name the subject in text.
 */
export function SubjectIcon({ subject, size = 46, className = "" }: { subject: string; size?: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-grid shrink-0 place-items-center rounded-[14px] bg-accent text-white dark:text-background ${className}`}
      style={{ width: size, height: size, boxShadow: "0 6px 16px color-mix(in srgb, var(--accent) 40%, transparent)" }}
    >
      <Icon name={subjectIconName(subject)} size={Math.round(size * 0.48)} />
    </span>
  );
}
