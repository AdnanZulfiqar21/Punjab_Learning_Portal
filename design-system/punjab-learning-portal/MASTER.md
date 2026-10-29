# Punjab Learning Portal — design system (MASTER)

Owner (2026-10-29): "ab ya sary skills use krty huwa apna portal design karo full to premium", then, after four drafts
of the home page, chose **draft C · Soft Glass** ("C done kr do"). The approved draft is
`draft-c-soft-glass.html` in this folder — match its look. This file is the single source of truth for the web portal;
page-specific rules go in `pages/<page>.md` and override it.

Style reference (ui-ux-pro-max, `--domain style`): **Glassmorphism** — frosted glass, translucent layered surfaces,
backdrop blur 10–20 px, 1 px light border, soft depth; light and dark supported. Combined with the skill's priority
rules: accessibility first (4.5:1 text, visible focus, keyboard, labels), touch targets ≥ 44 px, no layout shift,
mobile-first (375 / 768 / 1024 / 1440), semantic tokens only, motion 150–300 ms respecting `prefers-reduced-motion`,
SVG icons (never emoji).

## Owner rules that override everything here (do not change)
1. Heading colours (memory `heading-color-scheme`): lesson title x.y = subject accent; x.y.z = `--heading`; x.y.z.w and
   headings inside lessons = `--subheading`. The chapter topic list (table of contents) stays plain text colour.
2. Dark-mode palette (PR #412): body `#ece9e3`, `--heading` champagne `#e6d3b3`, `--subheading` `#8fadde`, muted subject
   accents. Light-mode colour values unchanged. Do not change any existing colour token value.
3. Chapter opening panel (CHAPTER-OPENING-01) stays (restyled in glass only if it keeps its content and colours).
4. Reader: English | Roman Urdu | Lecture tabs; exercises/papers in Practice; "Class 11 / Class 12" (never XI/XII);
   comparison answers as tables; green tip boxes; code colours (CODE-HIGHLIGHT-01); Run boxes.
5. **Lesson text stays on a solid surface** (no blur behind running text, figures, tables or code) — glass is for chrome,
   cards, heroes and navigation only. Readability beats effect.
6. No invented academic content or fake numbers anywhere (no testimonials, ratings, student counts).

## Look (from draft C)
- **Background:** a soft radial gradient mesh fixed behind the page — light: teal `#bfe3ee` top-left, lavender `#d9d6f7`
  top-right, peach `#fbe3cf` bottom over `--background`; dark: the same shapes at low strength (teal/indigo/amber at
  ~12–16 % over `#121412`). Subject pages may tint the mesh with the subject accent.
- **Glass surface:** `--glass-bg` light `rgb(255 255 255 / .62)`, dark `rgb(27 30 27 / .62)`; `--glass-border` light
  `rgb(255 255 255 / .75)`, dark `rgb(255 255 255 / .08)`; blur 16 px; `--shadow-glass` light
  `0 8px 30px rgb(15 29 43 / .06)`, dark `0 8px 30px rgb(0 0 0 / .35)`. Fallback when `backdrop-filter` is unsupported
  or `prefers-reduced-transparency: reduce`: solid `--surface`.
- **Radius:** cards 24 px, inner elements 16 px, chips/buttons full pill.
- **Header:** floating, sticky `top: 12px`, inside the page container, glass, radius 24; brand left; nav right (Learn,
  Practice, Search, Help, Account) with the active item in the accent and `aria-current`; on phones a menu button opens
  the same links.
- **Hero (hubs):** centred eyebrow (accent, uppercase, tracking .15em), display headline (Outfit 700, 52/56 desktop,
  34/40 phone), muted lead, pill buttons (primary = dark `--foreground` bg with `--background` text; secondary = glass),
  optional glass "Continue" card with a gradient progress bar.
- **Cards:** glass, radius 24, padding 22 px; interactive cards lift 2 px with a slightly stronger shadow and the accent
  border on hover/focus-visible.
- **Subject identity:** a 46 px rounded tile in the subject accent with a white SVG icon (Biology dna, Chemistry flask,
  Physics atom, Computer Science code) and a soft accent glow.
- **Typography:** **Outfit** (headings, display, brand; 600/700) and **Inter** (body/UI 400/600) via `next/font/google`;
  code Geist Mono; Urdu script Noto Nastaliq Urdu. Lesson body 17/28.
- **Footer:** centred muted line on the mesh; links Learn · Practice · Help · Pricing.

## Tokens (add to `globals.css`; keep every existing token and value)
`--glass-bg`, `--glass-border`, `--shadow-glass`, `--mesh-1/2/3` (light/dark), `--radius-card 24px`, `--radius-inner 16px`;
expose as Tailwind theme names where useful (`bg-glass`, `border-glass`, `shadow-glass`, `rounded-card`).

## Components (`apps/web/src/components/`)
`Icon` (Lucide paths, ISC, credited), `SubjectIcon`, `Button`/`ButtonLink` (primary, secondary-glass, ghost; md 44 px,
lg 48 px; pill), `GlassCard` (static/interactive), `PageHero` (eyebrow, title, lead, actions, children), `SectionHeader`,
`StatChip`, `ProgressBar` (labelled, `role="progressbar"`). Existing `ui.tsx` exports keep their API.

## Quality gates (every redesigned page)
Text ≥ 4.5:1 on glass in light and dark (measure against the glass colour over the mesh); focus visible; touch ≥ 44 px;
no horizontal scroll at 375 px; reduced motion and reduced transparency respected; skeletons sized (no layout shift);
axe (`@axe-core/playwright`) with no serious/critical violations.
