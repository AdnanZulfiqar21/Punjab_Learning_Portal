# Claude UI handover

**18 October 2026.** Branch `feat/bio-xi-ch1-pilot` (based on Cursor's `feat/topic-reader` `8ea7a65`). Class XI Biology Chapter 1 pilot: the Learn path, chapter and topic reader on iPhone and web, the full chapter in English and Roman Urdu as private drafts, and the original figures. Nothing in the chapter is academically reviewed or published.

## What the iPhone is doing

Installed build **0.1.0 (2)** (commit `c9028c7`) is the last build on the phone until the owner installs build 3. Build 3 (`ios.buildNumber` `3`) is built from this branch; its id, commit and install page are recorded in `docs/runbooks/iphone-preview.md` once the EAS build page shows a finished artifact. Bundle `pk.punjablearningportal.student.preview`, no over-the-air updates, API origin baked in: `http://172.20.10.2:8100` (the computer's Wi-Fi address on 18 October; recheck before building).

The API the phone talks to must listen on `0.0.0.0:8100` against the development database `portal` (migration head `f8a21c6d4e90`), where the pilot drafts were imported on 18 October (`content/tools/import_lessons.py`). The phone shows the drafts only when signed in as a staff account that covers Class XI Biology (dev seed `studio-author@example.com`); a learner or guest sees the honest "isn't ready yet" state on every topic, because nothing is published.

Nothing here was checked on the physical phone by Claude. Browser checks (Playwright, Chromium desktop and the pane) cover the web; the native screens were typechecked, linted and host-tested, not run on a device or simulator.

## Shared interfaces (Cursor: additive only)

- **Blocks.** New block `model3d` (`blocks.py`, renderer 2 on web, Android and iOS; reviewed fallback mandatory): `model`, `poster_asset_version_id`, `frames[]` (≤48 archived stills of one turn), `alt`, `caption`, `long_description`, `labels[]`, `fallback`. `assets.block_refs` lists its poster, frames and fallback, so publication, packs and imports check them like diagrams. Native renderer is `NATIVE_RENDERER_VERSION = 2`; web `WEB_RENDERER_VERSION = 2`. Register renderer 2 in the client manifest of the next native build (CLIENT-FLOOR-01) before any lesson with `model3d` is published; until then older clients get the fallback still.
- **Imports.** A lesson row may carry `language` (`en`, `ur`, `roman_ur`) and `variant_of` (the base lesson's `external_id` or id in the same chapter). The variant joins the base's concept (`concept_id`), takes its topic, and is `translation_origin: human`. A variant must be imported after its base. Import preview now runs `assets.check_references` on every body, so a lesson naming an unarchived asset version is an error at preview, not at submit.
- **Reading.** `GET /v1/topics/{id}/lesson?language=` picks the variant by concept; `available_languages` and `requested_language_missing` say what exists. Unchanged shape.
- **Profile.** The Learn choice and the reader language use `PUT /v1/me/profile` (`grade`, `stream`, `subjects`, `explanation_language`) for signed-in learners; guests keep them on the device (mobile `learner-prefs.json`; web cookies `portal-learn`, `portal-reading-language`, HttpOnly, no personal data).
- **Discovery.** `GET /v1/discovery?grade=&track=` already filters a class's books by group; the UI never lists subjects itself. The ICS note comes from the API's track list.
- **Contracts** regenerated (`packages/contracts`): `model3d` schema; no removed fields.

## Screens (files with functional layout, not a theme)

Mobile (`apps/mobile/src`):
- `app/(tabs)/index.tsx` Learn: class → group chooser (`components/learn-context-picker.tsx`), compact context row with **Change**, **Continue reading** only from a real reading position, subject cards for that class and group (accent per subject), free previews for that class, "Your dashboard and tests" link. Dashboard meters moved to `app/dashboard.tsx` (also linked from Account).
- `app/chapter/[id].tsx` compact header, intro folded after three lines, topics next, offline save as one quiet row (`components/offline-pack.tsx`), previous/next.
- `app/topic/[id].tsx` sticky **English | Roman Urdu** control (`Segmented`), honest note when a language is missing, **Draft preview** chip for staff previews, lesson, previous/next. Switching languages returns to the same block (both variants share one block structure; `onBlockLayout` tracks block positions).
- `components/lesson-blocks.tsx` renderer 2: comparison tables as cards (`lib/lesson-tables.ts`), `model3d` → `components/model3d.tsx` (poster, then drag-to-rotate turntable of archived stills; arrow buttons and adjustable accessibility actions; frames load on request; nothing spins on its own), labelled callouts, folded long descriptions, figure plates at 4:3.
- `constants/theme.ts` warm neutrals, `SubjectAccents` (Biology emerald); `hooks/use-theme.ts` `SubjectAccent` provider. `components/ui.tsx` adds `subheading`, `Chip`, `Segmented`, `LinkButton`.
- `lib/learn-context-core.ts`, `lib/reading-language-core.ts`, `lib/prefs.tsx` (+ `prefs-store`): the rules and the device store. Host tests in `tests/learn-context.test.ts`.

Web (`apps/web/src`):
- `app/learn/page.tsx` same flow; `app/actions/learn.ts` server actions (`chooseLearnContext`, `chooseReadingLanguage`). Until a class and group are chosen, every book is still listed (Class XI and XII apart).
- `app/learn/chapter/[chapterId]/page.tsx` topics first (links outside the outline toggle, so no nested controls), then the published lessons section (kept: it is where published lessons are read in place and where reading position, notes and completion live), textbook panel without source ids.
- `app/learn/topic/[topicId]/page.tsx` sticky language control, Draft preview chip, blocks with ids `b0…` and `components/keep-place.tsx` (returns to the same block after a switch).
- `components/lesson-blocks.tsx` renderer 2; `components/model3d-figure.tsx` (turntable with pointer drag and arrow keys; `role=slider`). Tables are real tables above 40rem and cards below (`globals.css .lesson-table`). Subject accents via `[data-subject]`.
- No live three.js in learner pages (JavaScript budget, PERF-01); `three` is a devDependency used only by `content/tools/figures/render.mjs`.

## Content

`content/lessons/xi/biology/README.md` describes the files, placeholders, import and rendering. Eight English lessons, eight Roman Urdu variants, eight coverage registers, ten original diagrams and six original 3D models (poster + 16 stills each). Draft stage only.

## Evidence

- API: `test_bio_pilot.py` (variant import, `model3d` references, reader language), plus the import, variants, reading, blocks and media-manifest suites; ruff, format and mypy clean.
- Web: `e2e/pilot-biology.spec.ts` (guest chooser; chapter order; honest unpublished topic; staff preview in English then Roman Urdu at the same place, turntable by keyboard; axe on each page). CI imports the pilot drafts before the journeys.
- Mobile: `pnpm test` (host tests), `tsc --noEmit`, `expo lint`. Not device evidence.
