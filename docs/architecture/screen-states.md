# Screen-state map (P02.S1.T3)

**What this is.** An inventory of the screen states the learner web app (`apps/web`) and the Android/iOS app
(`apps/mobile`) show today, route by route. It was written on 21 October 2026 against `main` at `764319e2`.

**What this is not.** It is not an approved design and it is not G02 gate evidence. G02 also needs approved responsive
designs and documented accessibility checks. This file records the current implementation and its gaps.

**Method.** Each cell was checked by reading the code. A cell either says what the learner sees and cites `file:line`,
or says `GAP` (no handling exists). `n/a` means the state cannot occur on that screen. "Global" means only the shared
mechanism in section 2 applies. Line numbers drift, so re-check a cite before acting on it.

**Path conventions.**

| Area | Paths are relative to |
|---|---|
| Web | `apps/web/src/` |
| Mobile | `apps/mobile/src/` |
| API | `apps/api/src/portal_api/` |

**Roadmap sources** (`Road Map/Punjab_Learning_Portal_Master_Roadmap_v2.2_Integrated_Written_Assessment.md`):

| Topic | Roadmap section |
|---|---|
| The state list | P02.S1.T3 |
| The five answer states | §6.1 |
| Update required for unknown block types | §5.4 rule 5 |
| Correction notices and score versions | §5.7 |
| The three meters and the "unavailable" rule | §6.6 |

The component-level specification is in [component-specs.md](component-specs.md) (P02.S2.T2).

---

## 1. The states

| State | Roadmap requirement | Where it lives in code |
|---|---|---|
| Loading | Part of P02.S1.T3 | Web: per-page `<Suspense>` fallbacks; there are no `loading.tsx` files. Mobile: `useRequest` plus `Loading` |
| Empty / no content | P02.S1.T3 requires that unavailable material is told apart from a technical failure | Per-page messages |
| Signed out / forbidden | Each error needs a useful next action | Web: redirect to `/signin?next=`. Mobile: auth states |
| Access expired (trial or plan) | P02.S1.T3, "access expired" | Web: `PlanStatus`. Mobile: `PlanCard`; locked lesson bodies |
| Offline / network error | P02.S1.T3, "offline" | Web: `ConnectionStatus`, `error.tsx`, `reach()`. Mobile: `ApiError` with kind `offline` |
| Validation error | P02.S1.T3 | Form-level alerts, mostly (see component-specs §3) |
| Conflict (409, revision) | P02.S1.T3, "conflict" | Per feature: `ATTEMPT_ELSEWHERE`, `NOTE_CHANGED`, mapping revision, studio item revision |
| Successful recovery | P02.S1.T3 | "Back online", retry success, re-sent queues |
| Update required | §5.4 rule 5: show the reviewed fallback, else an explicit "update required to view this item", and block attempt start | Unknown-block fallback in both renderers; mobile `VersionGate` |
| Score revised | §5.7: a derived notice; earlier versions preserved | Result pages; progress report |
| Answer states | §6.1: `selected` (local only), `saving`, `saved` (server receipt), `pending` (queued offline or unacknowledged), `rejected` (with reason). "Selected" is never shown as "saved" | `lib/answer-state.ts` on both clients, which adds `empty` (not answered) |

---

## 2. Shared mechanisms

### 2.1 Web (`apps/web/src/`)

| Mechanism | Behaviour | Cite |
|---|---|---|
| Loading | Each page wraps its data in `<Suspense>`. `SkeletonLines` and `SkeletonCards` render `role="status" aria-live="polite"` with an sr-only label. There are no `loading.tsx` files. | `components/ui.tsx:52-72` |
| Technical failure (data reads) | `getJSON` throws `ApiUnavailableError` on a network error, an 8 s timeout, or any status other than 404/410. 404 and 410 come back as values. | `lib/api.ts:26-51` |
| Technical failure (session calls) | `api()` returns any non-2xx status as `{ok:false,status}`. It throws only when `fetch` itself rejects, and does not catch that rejection. | `lib/session.ts:30-48` |
| Error boundary | The only boundary is the root `app/error.tsx` (there is no `global-error.tsx`). It shows "We couldn't load this page", "The learning service did not respond. Your progress is not affected.", a reference digest, "Copy details for support" and "Try again" (`retry()`, Next 16.4). It uses `role="alert"` and the same copy for every error, staff pages included. | `app/error.tsx:6-27` |
| Not found | One page for both 404 and 410: "This page isn't available… or is no longer part of the current textbook catalogue", with a "Browse all chapters" link. | `app/not-found.tsx:3-16` |
| Offline banner | `ConnectionStatus` listens for the browser's `offline` and `online` events. Offline: "You're offline. Pages need a connection; answers you choose in a test are kept on this device and sent when you're back." Back online: "You're back online." for 4 s. Both use `role="status"`. | `components/connection-status.tsx:14-37`; mounted at `app/layout.tsx:47` |
| Offline page | In production a service worker serves `public/offline.html` for failed navigations only ("You're offline… Try again"). The page has its own inline colours, which differ from the tokens in `globals.css`. | `apps/web/public/sw.js:22-26`; `apps/web/public/offline.html` |
| Incidents | Open incidents appear above the content as `role="status"`, labelled "Service status". The banner hides itself if `/v1/status` fails. | `components/incident-banner.tsx:13-29`; `app/layout.tsx:88-90` |
| Signed out | `currentUser()` returns null on 401 **or 403**, so pages redirect to `/signin?next=…`. The header link checks only whether a cookie exists. | `lib/session.ts:56-65`; `components/account-nav.tsx:5-14` |
| Plan and trial | `PlanStatus`: active (ok tone, with the allowance); trial available (Start trial); otherwise warn "Your free trial ended on {date}" or "No active plan" with the reason. The ended/no-plan notice has no link. | `components/plan-status.tsx:17-64` |
| Mock running | A 409 with `MOCK_IN_PROGRESS` is mapped to `MockRunningNotice` ("Your mock test is still running", "Back to your mock"). | `lib/practice.ts:18-21`; `components/mock-running.tsx:5-13` |
| Server actions while offline | `reach()` turns a request that never arrives into an ordinary failure value. Only the MCQ runner and the written runner use it. Any other action rejects, and `error.tsx` replaces the page, losing typed input. | `lib/reach.ts:4-10` |
| Update required | Unknown block types render the reviewed fallback, otherwise `role="note"` "This part of the lesson needs a newer version of the app to display." The web app has no client minimum: the API treats the web as always current. | `components/lesson-blocks.tsx:238-245`; API `modules/system/clients.py:16` |
| Answer states | `answerState()`, `PALETTE_LABEL` and `stateLine()`. The file is byte-identical to the mobile copy, but nothing in CI enforces that. | `lib/answer-state.ts:5-42` |

### 2.2 Mobile (`apps/mobile/src/`)

| Mechanism | Behaviour | Cite |
|---|---|---|
| Root | The splash stays up until the API origin has loaded. Provider order is `VersionGate` › `AuthProvider` › `DisplayProvider` › `PrefsProvider`. The attempt screen has `gestureEnabled: false`. | `app/_layout.tsx:12-58` |
| Update required | `VersionGate` asks `api.clientPolicy` once per launch; a failed check is ignored until the next start. `update_required` replaces the whole app with "Please update the app" and the version text, with no button. `update_soon` shows a warn Notice "An update is needed soon" with the date. | `components/version-gate.tsx:16-48` |
| HTTP 426 | `UPDATE_REQUIRED` is mapped to kind `server` ("Please update the app to continue."). It is **not** routed to `VersionGate`, so it appears as a generic error. | `lib/api.ts:207` |
| Request lifecycle | `useRequest` has the states `loading`, `error(ApiError)` and `success`, with abort on unmount and an explicit `retry()`. There is no automatic retry. | `hooks/use-request.ts:5-42` |
| Error mapping | Fetch throws become `offline` ("Can't reach the learning service. Check your connection and try again."). Status mapping: 404/410 → `not_found`; 401 → `unauthorized`; 422 → `invalid`; 409 → `conflict`; everything else, **including 403, 426, 429 and 503**, → `server`. `problem.code` is never read; only `code_reason` is. | `lib/api.ts:194-210` |
| Timeouts | A 15 s timeout (120 s for uploads) applies **only when the caller passes no abort signal**. Every `useRequest` loader passes one, so reads have no timeout and a stalled connection spins forever. | `lib/api.ts:194`; e.g. `app/mocks.tsx:32` |
| Auth | The states are `loading`, `signed_out`, `unavailable(error)` and `signed_in`. Offline at start-up gives `unavailable`, and only the Account tab shows it as an error. Other screens treat `unavailable` as signed out. | `lib/auth.tsx:16-58` |
| Sign-out | Deletes note drafts, answer queues, study packs, the progress queue and written page drafts **without checking for unsent work**. | `lib/auth.tsx:82-88` |
| Loading view | `Loading`: an accent spinner plus a muted label. The container has `accessible`, an `accessibilityLabel` and `aria-busy`, but no live region. | `components/ui.tsx:123-133` |
| Error view | `ErrorState` (`accessibilityRole="alert"`). Titles: "This isn't available" for `not_found`, "You're offline" for `offline`, otherwise "Something went wrong". Shows the message, then "Try again" (or "Go to Learn" for `not_found`) and "Reference: {12 chars}". The reference also appears on offline errors that never reached the server. | `components/ui.tsx:135-169` |
| Not found route | "This page isn't here" with a "Go to Learn" button. | `app/+not-found.tsx:16-22` |
| Plan and trial | `PlanCard`: device authorisation required; active; trial available; ended or no plan (warn). | `components/plan-card.tsx:46-111` |
| Mock running | Same notice as the web, with a "Back to your mock" button. | `components/mock-running.tsx:12-28` |
| Persistent queues | Answer ops: one file per attempt, holding `{ops, submitKey}`, **not account-scoped**. Progress ops (completion and notes): per account; a temporary error stops the flush, and **any other error drops the op silently**. `enqueue` does not flush. | `lib/op-store.ts:5-45`; `lib/progress-queue-core.ts:29-55`; `lib/progress-queue.ts:45-50` |
| Offline packs | `PACK_FORMAT=1`. A pack that is too new or expired is read as `null`, the same as "no pack". | `lib/study-packs-core.ts:5-32`; `lib/study-packs.ts:90-101` |
| Network status | No NetInfo. Offline is only ever inferred from a failed request. | (none) |

### 2.3 Coverage by state (summary)

- **Loading.** Every learner route has a labelled loading state.
  - Mobile reads have no timeout (§2.2), so loading can last forever. The lecture view's "Checking for a lecture" spinner never ends on an error (`app/topic/[id].tsx:168`).
- **Empty versus unavailable versus failure.** Handled on the main learning pages, but many failures are shown as content states (gap G5):
  - shown as "not found": web topic, help ticket, help article, linked written test;
  - shown as "empty": help list, chapter lessons when the request returns 404/410, mock sessions;
  - shown as "pending": written result → "Waiting for a teacher";
  - shown as "coming": lecture.
- **Signed out.** Web redirects consistently. Mobile shows `unavailable` (started offline) as signed out on about 15 screens (gap G2).
- **Access expired.**
  - Web uses `PlanStatus` on practice and written practice only. The dashboard has no plan notice.
  - The web topic reader never reaches its locked branch (gap G1).
  - Mobile collapses 403 codes such as `ACCESS_REQUIRED` into "Something went wrong".
- **Offline.**
  - Strong in both runners: a local queue, re-send, honest per-question states.
  - Elsewhere the web replaces the page with `error.tsx`, and mobile shows `ErrorState`.
- **Validation.**
  - Only the web sign-in form ties errors to fields.
  - Everything else shows one form-level alert, or disables Submit without saying why.
- **Conflict.** Fully handled for:
  - studio item revisions;
  - lesson notes (`NOTE_CHANGED` / `NOTE_DELETED`);
  - the written page map (revision 409);
  - marking (`expected_version`);
  - attempt "open on another device".

  `MOCK_IN_PROGRESS` gets its notice only on some routes.
- **Recovery.** "You're back online" (web, global); runner status returns to "{n} answered · all saved"; note and map "Saved" lines. Mobile has no reconnect trigger in the runner.
- **Update required.**
  - Block-level fallback exists on both clients.
  - Nothing blocks starting an attempt whose form contains an item this client cannot render (§5.4 rule 5).
  - Mobile has the whole-app gate, but a 426 response bypasses it.
  - On the web the wording "newer version of the app" is wrong, since the website cannot be updated by the learner.
- **Score revised.**
  - Result pages show "Updated {date}" plus the reason, and treatment badges; web also shows score history.
  - The web progress report marks "updated after review".
  - Dashboards (web and mobile) do not mark revised scores.
  - No correction notice appears during an active attempt (§5.7 "During an active attempt").
- **Answer states.** All five are implemented with identical logic on both clients (section 3). The gaps are in the summary line, colour coding and announcements.

---

## 3. The five answer states (practice and mock runner)

The runners are web `app/practice/attempt/[id]/attempt-runner.tsx` (W) and mobile `app/attempt/[id].tsx` (M). Both use
the shared `lib/answer-state.ts`.

### 3.1 Derivation

- `answerState(status, {sending, held})` passes any status other than `pending` through. A `pending` status becomes:
  - `saving` when a request is carrying it;
  - `pending` when it is held;
  - `selected` otherwise.

  Cite: `lib/answer-state.ts:8-12`.
- "Held" means any of: restored from an earlier session, the last send failed, the connection is retrying, or the test is held on another device (W:296; M:285-288).
- A choice sets the status to `pending` and is debounced for 400 ms, under the §10.5 limit of 500 ms (W:16, W:233-244; M:24, M:240-250).
- `saved` is set only when the server returns `accepted` for that op (W:135-136; M:129). Answers already on the server load as `saved` (W:76; M:90).
- `rejected` keeps the chosen option and sets a reason from the `REASON` map (W:57-64, W:137-139; M:27-34, M:130):
  - `stale`: "A newer answer from another tab or device is already saved."
  - `invalid`
  - `late`: "…after the time limit…"
  - `finalised`
  - `locked`
  - `conflict`

  The mobile wording differs slightly ("another device"; `conflict` lacks "…and wasn't applied").

### 3.2 Display

| State (§6.1 name) | Line under the options (`stateLine`) | Web palette cell (W:20-27) | Mobile palette cell (M:355) | Palette accessible label (`PALETTE_LABEL`) |
|---|---|---|---|---|
| `empty` (code only) | none | `border-border bg-surface` | `surface` | "not answered" |
| `selected` | "Selected · not sent yet" | `border-accent bg-accent-soft` | `accentSoft` | "selected, not sent yet" |
| `saving` | "Saving…" | `border-warn bg-warn-soft` | `warnSoft` | "saving" |
| `saved` | "Saved" | `border-ok bg-ok-soft` | `accentSoft`, **the same as `selected`** | "saved" |
| `pending` | "Not saved yet: kept on this device and sent again when the connection is back"; or, when held elsewhere, "Not saved: kept on this device until you continue here" | `border-dashed border-warn bg-warn-soft` | `warnSoft`, **the same as `saving`** | "not saved yet, kept on this device" |
| `rejected` | "Not saved: {reason}" | `border-danger bg-danger-soft` | `dangerSoft` | "not saved" |

**Text colour of the state line.** Web uses `text-danger` for rejected, `text-warn` for pending, and muted otherwise
(W:438-440). Mobile does the same with `c.danger` and `c.warn` (M:418-420). Neither line is a live region, so a
change is not announced.

**Palette cell.**
- Web cells are 36 px buttons. The current question has `aria-current="step"` and a 2 px accent ring. A flag shows as a `⚑` badge, which is `aria-hidden`; the flag is spoken through the label (W:361-382).
- Mobile cells are 40 × 40 Pressables. The current question is shown only by its border and is not exposed to screen readers. A flag appears as " ⚑" in the text (M:352-370).
- Sighted users get only colour on both clients. The web adds a dashed border for `pending`. No state has an icon.

**Option rows.**
- The chosen option is highlighted (web `border-accent bg-accent-soft`, W:401) whatever its save state. The save state is shown only by the line under the options.
- A rejected option stays checked.

**Summary line.**
- The header line is `role="status" aria-live="polite"` on the web (W:341-347). On mobile it is a polite live region, which works on Android only (M:342-344).
- It reads "Offline: answers are kept on this device and will be sent again" while retrying. Otherwise it reads "Saving {n}…", where *n* counts every item with status `pending`, so `selected` and held items are included. Otherwise it reads "{answered} answered · all saved".
- **Rejected items are not counted**, so "all saved" can appear while answers are rejected (W:298-299; M:289-290).

### 3.3 Queue, retry, timer and submission

| Behaviour | Web | Mobile |
|---|---|---|
| Persistence of unacknowledged ops | `localStorage` key `practice-queue:{id}`, holding `{ops, submitKey}`. If storage is unavailable the ops are still sent; nothing is shown as saved early (W:31-55) | One file per attempt (`lib/op-store.ts:5-33`) |
| Restore after reload or restart | Restored ops are shown as `pending` and re-sent (W:110-119, W:191-199) | The same (M:190-208) |
| Reconnect trigger | The `online` event re-sends (W:203-207) | **None**. Re-sends happen on AppState active or inactive (M:209-212) and on the backoff timer |
| Retry and backoff | Starts at 2 s and doubles to 15 s, plus 0-500 ms jitter; resets on success (W:161-173) | The same (M:150-174) |
| Batch | At most 50 ops; one request in flight (W:150-156) | The same (M:142-144) |
| Timer | Display only. The offset comes from `server_now` on the first tick, so "--:--" shows until then. Pre-flush at D − 5 s; flush at D; refresh after C + 1.5 s. Text turns danger under 60 s (W:101-107, W:209-231, W:349-357) | The same. Its `accessibilityLabel="Time remaining"` replaces the value for screen readers (M:219-238, M:345-349) |
| Held on another device | A `role="alert"` panel: "This test is open on another device." and "Continue here" (W:319-335) | An **info** Notice and "Continue here". If continue-here fails, the error is written to `submitError`, which renders only inside the confirm panel, so **it is invisible** (M:314-340, M:461) |
| Flags | Optimistic, with `aria-pressed`. A failure rolls back and shows a `role="alert"` message (W:246-262, W:417-432) | Optimistic. The error is shown in danger text with no live region (M:296-312, M:406-414) |
| Immediate feedback "Check answer" | Shown only once the answer is `saved`. **A failure is ignored** (W:264-271, W:433-437) | The same; errors are swallowed (M:252-261) |
| Submit | "Finish test" opens an inline `role="dialog" aria-modal="false"` showing answered, not answered, still being saved and flagged counts, with links back to flagged questions. The idempotency key is persisted before sending. An offline failure shows `role="alert"` "Can't reach the service. Nothing was lost; submit again when you're back online." and the button becomes "Try again". On success, `router.replace` to the result (W:273-292, W:464-518; `app/actions/practice.ts:131-145`) | A confirm panel with the same content, and the same key handling (M:263-283, M:438-465) |
| Session expiry or access ending mid-test (401/403 on save) | Becomes `kind:"error"` (`app/actions/practice.ts:123`), retried forever and **labelled "Offline"**, with no sign-in path | The same (M:169-174) |

### 3.4 Against §6.1

- **Met on both clients:**
  - All five names exist.
  - `selected` is never shown as `saved`.
  - `saved` needs the server's receipt.
  - `pending` survives a reload or restart.
  - `rejected` carries a reason.
- **Not met:**
  - "Colour is never the sole signal": for sighted users the palette is colour only, and on mobile two pairs of states share a colour.
  - The summary line can say "all saved" while answers are rejected, and "Saving" while answers are only held.
  - State changes are not announced (no live region on the per-question line; mobile has no iOS announcements at all).
  - 401 and 403 are presented as offline.

---

## 4. Learner web routes (`apps/web/src/`)

In every row, "global" refers to section 2.1. Unless a row says otherwise:
- offline means the global banner, with an action rejection going to `error.tsx`;
- update required means the `LessonBlocks` fallback wherever blocks are rendered;
- the web has no client-minimum check anywhere (gap G8).

### `/` (home): `app/page.tsx`, `components/dashboard.tsx` (D)

| State | Shows | Cite |
|---|---|---|
| Loading | `SkeletonLines` "Loading" | `app/page.tsx:13` |
| Empty | "Choose your class and subjects" with "Set up your profile"; "Nothing in progress." with "Browse chapters"; "Nothing due today."; "No mock is scheduled."; "No submitted tests yet." with "Take a practice test" | D:40-48, 95-101, 109-111, 138, 186-192 |
| Unavailable vs failure | A dashboard request that is not OK shows warn "Couldn't load your dashboard" (role=note, no retry). When signed out, a discovery failure is swallowed and the generic intro is shown. | `app/page.tsx:23-25`, 31-38 |
| Signed out / forbidden | Anonymous intro. A 403 on `/v1/me` is treated as signed out. | `app/page.tsx:21`; `lib/session.ts:61` |
| Access expired | GAP: no plan notice on the dashboard | D |
| Offline / recovery | Global | — |
| Conflict | "Unfinished tests" list with "Continue" links (so a test can be continued on this device) | D:49-76 |
| Meters | Three separate cards. "Unavailable" plus the API's reason when `percent` is null | D:142-171 |
| Score revised | GAP: recent results ignore `score_version` (the progress report shows it). "Not scorable" and "N scheduled mock result(s) waiting for release" are shown. | D:181-185, 201-207 |
| Validation / update | n/a | — |

### `/learn`: `app/learn/page.tsx`

| State | Shows | Cite |
|---|---|---|
| Loading | `SkeletonCards` "Loading subjects" | :38, :74 |
| Empty | "No {class} {group} books yet". With no context chosen and no books at all: GAP (only a heading is rendered) | :201-204; :251 |
| Unavailable vs failure | A discovery 404/410 shows warn "Couldn't load these subjects" or "Couldn't load the books". Other failures go to `error.tsx`. A "Continue reading" failure is silent. | :177-183, :249; :126-127 |
| Signed out | Anonymous. The choice is kept in a cookie: "Chosen on this device · sign in to keep it" (text, not a link) | :64 |
| Conflict | Warn "More than one edition is effective today" | :195-200, :269-274 |
| Validation | Native `required` radios. An invalid post redirects silently. | :96, :107; `app/actions/learn.ts:54` |
| Access / offline / recovery / update / score | n/a or global | — |

### `/learn/[grade]/[subject]`: `app/learn/[grade]/[subject]/page.tsx`

| State | Shows | Cite |
|---|---|---|
| Loading | `SkeletonCards` "Loading chapters" | :14 |
| Empty | GAP: "0 chapters" with no message | :37 |
| Unavailable vs failure | A bad grade or a 404/410 → `notFound()` (404 and 410 are not told apart). Other failures go to `error.tsx`. Warn "Part of the supplied textbook file is missing" | :23-26, :40-46 |
| Other states | n/a (public page) | — |

### `/learn/chapter/[chapterId]`: page (P), `components/study-tools.tsx` (ST)

| State | Shows | Cite |
|---|---|---|
| Loading | "Loading chapter". Topics render without stars until favourites load. "Loading lessons" | P:33, P:81, P:89 |
| Empty | "No topics are recorded for this chapter."; "No reviewed lessons are published for this chapter yet…" | P:78-79, P:192-196 |
| Unavailable vs failure | A 404/410 chapter → `notFound()`. A 404/410 lesson list becomes `[]`, which shows the empty text. If favourites fail, the stars are hidden silently. | P:42-44, P:143, `lib/api.ts:43`, P:271-272 |
| Signed out / access expired | Locked lesson box: "This lesson is included with a plan or the free 30-day trial." with "Start your free trial or sign in". The same text appears for an ended trial. For a guest, `/account` redirects to sign-in and the chapter is lost as the return path. | P:222-231 |
| Offline | Notes: the draft is kept in `localStorage`; `role="alert"` "You're offline. Your note is kept on this device…"; "Not saved yet (kept on this device)." The reading tracker swallows errors. A favourite reverts silently. "Save formula" failure: "Couldn't save. Try again." | ST:47-54, 73-77, 140, 143-147, 185-186; `components/reading-tracker.tsx:24` |
| Validation | Note `maxLength` 5000 | ST:113 |
| Conflict | Note 409 `NOTE_CHANGED` / `NOTE_DELETED`: a `role="alert"` panel with "Keep mine" and "Use the other version" / "Discard mine" | ST:148-167; `app/actions/study.ts:17-18` |
| Recovery | "Saved. Only you can see this note." / "Note deleted." (`role="status"`, polite); "✓ Completed: undo" | ST:136-139; P:247 |
| Update required | `LessonBlocks` fallback, else "needs a newer version of the app" | `components/lesson-blocks.tsx:238-245` |
| Score revised | n/a. The lesson shows "version N · published {date}" and a language fallback note | P:200-212 |
| Silent failure | GAP: "Mark as completed" ignores its result | `app/actions/lessons.ts:12` |

### `/learn/topic/[topicId]`: `app/learn/topic/[topicId]/page.tsx`

| State | Shows | Cite |
|---|---|---|
| Loading | `SkeletonLines` "Loading lesson" | :68 |
| Empty | "This topic's lesson isn't ready yet"; lecture: "The lecture for this topic is coming" | :166-167; :159-163 |
| Unavailable vs failure | GAP: **any** non-OK status (401, 403, 404, 410, 5xx) → `notFound()`. A failed lecture request shows "coming". | :80-81; :89-90 |
| Signed out | Anonymous reading is allowed | :80 |
| Access expired | **GAP (defect).** The API returns `body: null` for a locked lesson (API `modules/content/reading.py:185`). The `!lesson?.body` test at :166 therefore wins, and the learner is told the lesson "has not been published". The locked notice (:168-174) and the lecture-locked notice (:140-146; it needs `readable`, :85) can never show. | :85, :166-174 |
| Offline | Global. The language switch is a plain form action. `KeepPlace` storage is try/catch. The video has no error state. | :97; `components/keep-place.tsx:19-26`; `components/lecture-view.tsx:53-55` |
| Validation | An invalid language redirects silently | `app/actions/learn.ts:66` |
| Update required | `LessonBlocks` fallback | `components/lesson-blocks.tsx:238-245` |
| Other | A missing language gives a `role="status"` note; a draft shows the chip "Draft preview" | :116-120, :128-132 |
| Conflict / recovery / score | n/a | — |

### `/search`: `app/search/page.tsx`

| State | Shows | Cite |
|---|---|---|
| Loading | "Searching" | :27 |
| Empty | "Enter at least two characters." (also on the first visit); "Nothing matches "{q}"…" | :86, :108-109 |
| Unavailable vs failure | A 404/410 shows warn "Search is unavailable". Other failures go to `error.tsx`. | :89-90 |
| Signed out / access | A locked hit says "Included with a plan or the free 30-day trial. Found by its title." (no link) | :158-159 |
| Validation | Native `required`, `minLength=2`, `maxLength=100` | :49-58 |
| Other | `role="search"`. The result count is not a live region. | :45, :93 |

### `/study`: `app/study/page.tsx`

| State | Shows | Cite |
|---|---|---|
| Loading | "Loading your study tools" | :24 |
| Empty | "No notes yet…", "No favourites yet…", "No formulas yet…" | :51-52, :75-76, :99-100 |
| Failure | Warn "Couldn't load your study tools" (no retry button). When the feature is off: "Not available on your account yet" | :42-44, :34-36 |
| Signed out | Redirect | :33 |
| Changed source | "This lesson has been updated since you saved this formula…" | :107-111 |
| Silent failure | GAP: formula "Remove" ignores its result | :116-120; `app/actions/study.ts:64-69` |

### `/practice`: page (P), `practice-builder.tsx` (B)

| State | Shows | Cite |
|---|---|---|
| Loading | "Loading practice options"; the submit button reads "Preparing…" | P:49; B:223 |
| Empty | "No approved practice questions yet" (also shown for an availability 404) | P:86-90; `lib/practice.ts:11` |
| Failure | Other availability errors go to `error.tsx`. If `getAccess` fails, `PlanStatus` is hidden and the builder is shown. | `lib/practice.ts:12`; `lib/access.ts:8` |
| Signed out | Redirect; a 401 from the action also redirects | P:60; `app/actions/practice.ts:51` |
| Access expired | `PlanStatus` with purpose "Practice tests". The builder is withheld while `!has_access`. | P:85-86 |
| Offline | GAP: `createPractice` has no `reach()`, so a failure goes to `error.tsx` | B:27-33 |
| Validation | Submit is disabled until the form is valid, with no reason given. Native min/max. The server message is `role="alert"`, with "You can ask for up to N." | B:60, 151-154, 171-176, 212-220; `app/actions/practice.ts:21,30` |
| Conflict | A 409 `MOCK_IN_PROGRESS` shows only the detail text, with no "Back to your mock" link. The idempotency key is reused on retry. | `app/actions/practice.ts:50-53`; B:24-33 |
| Recovery | Redirect to the new attempt | `app/actions/practice.ts:57` |

### `/practice/attempt/[id]`: `page.tsx` (P), runner (W)

| State | Shows | Cite |
|---|---|---|
| Loading | `SkeletonLines` "Loading your test"; the timer shows "--:--" until its first tick | P:15; W:351-352 |
| Unavailable vs failure | A bad id or a 404/422 → `notFound()`. Other failures go to `error.tsx`. | P:26-28; `lib/practice.ts:28-29` |
| Signed out | Redirect to `/signin?next=/practice/attempt/{id}`. **Expiry mid-test is shown as offline** (§3.3). | P:25 |
| Access expired | GAP: a 403 on save is retried and labelled offline | `app/actions/practice.ts:123` |
| Offline | The per-question `pending` state; header "Offline: answers are kept on this device…" with "About saving"; offline submit gives an alert and "Try again" | W:341-348, W:496-503 |
| Conflict | `ATTEMPT_ELSEWHERE` panel with "Continue here"; per-op rejections with reasons; a 409 `finalised` applies the results and refreshes; `MOCK_IN_PROGRESS` on load → `MockRunningNotice` | W:319-335, W:57-64, W:174; P:29-35 |
| Recovery | Retry resets; the header returns to "{n} answered · all saved"; ops from an earlier session are re-sent; "Continue here" refreshes then flushes | W:168-173, W:191-199, W:304-315 |
| Submitted | "Test submitted" with ok "Time is up" or "Submitted", "{a} of {q} questions answered. Receipt {8}."; warn "Some last changes weren't counted"; "See your result" | P:36-56 |
| Update required | Stem, options and passage go through `LessonBlocks`. **GAP:** attempt start is not blocked for a form containing an item this client can't render (§5.4 rule 5). Only publication validation guards it. | W:391-405; API `modules/content/blocks.py:291-298` |
| Score revised | GAP: no adjudication notice during an active attempt (§5.7: "excluded from score / credited / key corrected") | W (none) |
| Answer states | Section 3 | — |

### `/practice/attempt/[id]/result`: `result/page.tsx` (R)

| State | Shows | Cite |
|---|---|---|
| Loading | "Loading your result" | R:26 |
| Empty | Not scorable: warn "This test can't be scored" / "Every question was withdrawn after review…" | R:71-74 |
| Unavailable vs failure | A bad id or a 404/422 → `notFound()`. Other failures go to `error.tsx`. | R:37-39; `lib/practice.ts:45-46` |
| Signed out | Redirect | R:36 |
| Conflict and pending | `MOCK_IN_PROGRESS` → `MockRunningNotice`. `RESULTS_PENDING` → "Your answers are saved" with the release time. `SCORING_PENDING` → "Submitted: your result is being prepared" (no refresh, no auto-refresh). Any other 409 → "Not submitted yet" with "Return to the test". | R:40-65 |
| Score revised | Notice "Updated {date}", the `revision_reason` and "Your earlier result stays in your history."; "Score history (N versions)"; per-item badges "Excluded after review" / "Credited to everyone" / "Key corrected"; excluded and credited counts; warn "Some last changes weren't counted" | R:81-85, R:114-125, R:176-177, R:90-91, R:93-103 |
| Other | Badges "Correct", "Incorrect", "Not answered" (text plus colour); "Report a problem with question N" | R:178-184, R:228-233 |

### `/practice/mocks`: page (P), `start-mock.tsx` (SM), `join-session.tsx` (JS)

| State | Shows | Cite |
|---|---|---|
| Loading | "Loading scheduled mocks", "Loading test patterns"; "Preparing your mock…" / "Joining…" | P:23, P:26; SM:30; JS:22 |
| Empty | "No mock tests yet" with a practice link. No sessions → nothing is rendered. | P:38-48, P:111 |
| Unavailable vs failure | Warn "Couldn't load test patterns". **GAP:** a failed sessions request is hidden (`!res.ok` → null), and a failed readiness request shows the badge "Not enough questions yet". | P:37, P:111, P:53-62 |
| Signed out | Redirect | P:35, P:109 |
| Access expired | "Mock tests are included with a plan or the free 30-day trial." with "Start your free trial or see your plan" | P:90-97 |
| Offline | GAP: actions have no `reach()` | SM:18-27; JS:14-19 |
| Conflict | A 409 (including `MOCK_IN_PROGRESS`) shows the detail as `role="alert"` text, with no link to the running mock | SM:32-36; JS:24-28 |

### `/practice/notebook`: page (P), `controls.tsx` (C)

| State | Shows | Cite |
|---|---|---|
| Loading | "Loading your notebook"; "Saving…" / "Preparing…" | P:25; C:38, C:65 |
| Empty | "Nothing here yet" with "Build a practice test" | P:41-50 |
| Failure | Warn "Couldn't load your notebook" | P:39 |
| Signed out | Redirect | P:34 |
| Conflict | Load 409 → `MockRunningNotice`. Review 409 → `role="alert"` text | P:36-38; C:67-71 |
| Offline / validation | GAP: a failed note save only re-enables the button, with no message | C:24, C:32-33 |
| Score revised | The status badge shows raw enum values ("voided", "mastered") | P:80-81 |

### `/practice/plan`, `/practice/progress`, `/practice/evidence`

| Route | State | Shows | Cite |
|---|---|---|---|
| plan | Loading | "Planning" | `app/practice/plan/page.tsx:27` |
| plan | Failure | Warn "Couldn't make a plan" | :70-78 |
| plan | Infeasible | Warn "About X short…" | :88-93 |
| plan | Empty | GAP: an empty schedule has no message | :94-105 |
| plan | Validation | Native min/max on minutes | :56, :60 |
| progress | Loading | "Preparing your report" | `app/practice/progress/page.tsx:20` |
| progress | Empty / pending | "No submitted tests yet"; "Results on the way" | :44-57 |
| progress | Failure | Warn "Couldn't prepare your report" | :31 |
| progress | Score revised | " · updated after review" when `score_version > 1` | :105 |
| evidence | Loading | "Working out your evidence" | `app/practice/evidence/page.tsx:29` |
| evidence | Failure | Warn "Not available" (vague title) | :60-63 |
| evidence | Meters | `<dl>` labelled with raw keys; "Unavailable" **without the reason** | :66-77 |
| evidence | Empty | GAP: no outcomes → an empty list | :78-96 |
| all three | Signed out | Redirect | plan :39; progress :29; evidence :40 |

### `/practice/written`: page (P), `written-builder.tsx` (WB)

| State | Shows | Cite |
|---|---|---|
| Loading | "Loading written practice"; "Preparing…" | P:26; WB:113 |
| Empty | "No written questions yet"; "Written practice isn't offered for this subject yet" (also shown for a 404) | P:70-77; `lib/written.ts:9` |
| Signed out | Redirect | P:37 |
| Access expired | `PlanStatus` "Written practice"; a pilot-only notice | P:63-69 |
| Capacity | "Written tests are paused…"; "Marking is full right now" | P:86-105 |
| Offline | GAP: no `reach()` | WB:23-29 |
| Validation | Submit is disabled until a chapter is chosen (no reason). Server errors are `role="alert"`. | WB:110, WB:103-107 |
| Conflict | Error text only | `app/actions/written.ts:78` |

### `/practice/written/[id]` and `/practice/written/linked/[formId]`

The full written-state labels are in section 6. Route-level states:

| Route | State | Shows | Cite |
|---|---|---|---|
| `[id]` | Loading | "Loading your written test" | `app/practice/written/[id]/page.tsx:14` |
| `[id]` | Unavailable vs failure | A 404/422 → `notFound()`. **GAP:** if the result request fails, the result is `null`, which shows "Waiting for a teacher". | :25-32 |
| `[id]` | Signed out | Redirect. Uploading without a cookie shows the error "Sign in to continue." with no link. | :24; `upload/route.ts:18` |
| `[id]` | Access expired | Warn "This test ended because your plan was withdrawn" | `written-runner.tsx:345-351` |
| `[id]` | Offline | Warn "You're offline"; the map, seal and transform actions go through `reach()`; reconnect re-sends the map | `written-runner.tsx:375-381`, :114-132 |
| `[id]` | Conflict | A map 409 shows a message and "Load the latest mapping" | `written-runner.tsx:224-225`, :625-633 |
| `[id]` | Recovery | "Saving…" then "Saved · revision N" (`role="status"`, polite) | `written-runner.tsx:625-627` |
| linked | Loading | "Loading your new practice test"; no pending state on "Start the new test" | `app/practice/written/linked/[formId]/page.tsx:20`, :64-71 |
| linked | Failure | GAP: **any** non-OK status → `notFound()`. A failed start shows one generic danger alert, "The test couldn't be started", whatever the status. | :31-33, :58-62 |
| linked | Access expired | Warn "Not enough written allowance" with "See your plan" | :73-75 |
| linked | Conflict | Already started → redirect to the attempt | :35 |

### Account, notifications, onboarding, pricing and sign-in

| Route | State | Shows | Cite |
|---|---|---|---|
| `/account` | Loading | "Loading your account" | `app/account/page.tsx:31` |
| `/account` | Failure | Sessions failure goes to `error.tsx`. **GAP:** the access, preferences, settings, trial-device and assisted-access sections drop silently on failure. | :50, :159, :168, :197, :211, :220 |
| `/account` | Signed out / re-auth | Redirect; deletion and data export redirect to `/signin?…&reason=reauth` | :47; `app/actions/privacy.ts:16` |
| `/account` | Access | `PlanStatus`; a start-trial error is `role="alert"` | :159-166; `components/start-trial-button.tsx:27-31` |
| `/account` | Offline | GAP: study settings save and video quality have no try/catch, so `busy` sticks and no message appears | `components/study-settings.tsx:46-65` |
| `/account` | Silent failures | GAP: remove trial device, sign out a session, sign out everywhere else | `app/actions/access.ts:21`; `app/actions/auth.ts:70,76` |
| `/account/exports` | States | "You haven't requested any exports yet."; job states Waiting / Preparing / Ready / Failed / Cancelled / Expired; failure warn "Couldn't load your exports". Cancel and retry ignore their results. | `app/account/exports/page.tsx:14-21`, :49-54, :70-91 |
| `/notifications` | States | "Loading notifications"; info "Nothing yet"; warn "Couldn't load notifications" (no button); "{n} unread" (`role="status"`). Opening and "mark all read" ignore their results. | `app/notifications/page.tsx:16`, :33-41 |
| `/onboarding` | States | "Loading your preferences"; "Saving…"; errors `role="alert"` reading "Please check: {raw API field}: {msg}" (no `aria-invalid`) | `app/onboarding/page.tsx:17`; `onboarding-form.tsx:109-119`; `app/actions/auth.ts:98-99` |
| `/pricing` | States | "Loading plans"; "No plans are on sale yet…"; warn "Couldn't load plans"; info "Buying isn't available yet" | `app/pricing/page.tsx:38-62` |
| `/signin` | Failure | GAP: if the API is down, the methods list is `[]`, which shows "Sign-in is not available in this environment" | `lib/session.ts:73-76`; `app/signin/page.tsx:48` |
| `/signin` | Re-auth | Info "Sign in again to continue" | `app/signin/page.tsx:16-19` |
| `/signin` | Validation | The only form with field errors: `aria-invalid` and `aria-describedby`, plus a form-level `role="alert"` | `sign-in-form.tsx:13-66` |

### Help

| Route | State | Shows | Cite |
|---|---|---|---|
| `/help` | Failure | **GAP:** a failed request becomes `[]`, which shows "No requests yet" | `app/help/page.tsx:39-41` |
| `/help/new` | States | "Sending…"; server errors `role="alert"`; success redirects to the ticket. Offline → `error.tsx`. | `new-ticket-form.tsx:57-63`; `app/actions/support.ts:34-38` |
| `/help/[id]` | Failure | **GAP:** any non-OK status → `notFound()` | `app/help/[id]/page.tsx:31-32` |
| `/help/[id]` | Screenshots | Type and size errors `role="alert"`; offline "…Check your connection and try again."; "Checking and adding your screenshot…" (not live) | `screenshots.tsx:33-72` |
| `/help/[id]` | Score revised | "The question was withdrawn / answer corrected after review… re-scored as a new score version" | `app/help/[id]/page.tsx:50-55` |
| `/help/articles` | States | "No matching articles"; warn "Help is unavailable right now" | `app/help/articles/page.tsx:38-39` |
| `/help/articles/[slug]` | Failure | **GAP:** any non-OK status → `notFound()` | `app/help/articles/[slug]/page.tsx:28-30` |

---

## 5. Mobile screens (`apps/mobile/src/`)

Codes used below:

| Code | Meaning |
|---|---|
| L | `Loading` |
| E | `ErrorState` |
| SO | A signed-out Notice, shown for `signed_out` **and** for `unavailable` |
| VG | `VersionGate` only |

Unless a row says otherwise, update required = VG plus the `lesson-blocks` fallback, and 403/426/429/503 = E "Something went wrong" with "Try again".

### Tabs

| Screen | State | Shows | Cite |
|---|---|---|---|
| Learn `(tabs)/index.tsx` | Loading | L "Loading", L "Loading your subjects" | :55, :62-63, :76 |
| Learn | Empty | Context picker; "No {Class} {group} books yet"; warn about overlapping editions | :64-65, :156-164 |
| Learn | Signed out / offline | **GAP:** auth `unavailable` is treated as a guest. Discovery offline → E. | :26-27, :77 |
| Learn | Recovery | "Saved to your profile." / "Kept on this device. Sign in to keep it with your account." | `components/learn-context-picker.tsx:46-50` |
| Practice `(tabs)/practice.tsx` | Loading | L "Checking your sign-in" / "Checking your plan" / "Loading chapters" | :35, :57, :157 |
| Practice | Empty | "No approved practice questions yet"; chapter rows "none yet" (disabled) | :159-163, :185, :211 |
| Practice | Signed out | "Sign in to practise" with "Go to Account" (also shown for `unavailable`) | :36-41 |
| Practice | Access | `PlanCard`; the builder is hidden unless `has_access`; a 403 on start → `FormError` with the detail | :61-62, :126-133 |
| Practice | Validation | "Choose at least two subjects for a custom mix."; Start disabled with " (at most 100 in one test)" (polite); 422 → message plus " You can ask for up to N." | :93-94, :260, :285-290, :128-131 |
| Practice | Conflict | GAP: `MOCK_IN_PROGRESS` → message only | :129-133 |
| Search `(tabs)/search.tsx` | States | L "Searching"; "Enter at least two characters."; "Nothing matches "{q}"."; locked-hit text; E | :58, :68-78, :94-98 |
| Account `(tabs)/account.tsx` | Loading | L for sign-in, sign-in options, plan and devices | :22, :38, :190, :199 |
| Account | Signed out | Sign-in form. OIDC → "Sign-in provider not yet connected". None → "Sign-in is not available in this environment". | :29, :42-49 |
| Account | Offline at start | The **only** screen that shows `unavailable` as an error with retry | :23 |
| Account | Validation | "Enter your email and password."; "Use at least 10 characters."; "Email or password is incorrect."; "Enter a valid email address."; deletion disabled until the email matches | :64-79, :107, :378 | <!-- pragma: allowlist secret -->
| Account | Conflict | GAP: a register 409 shows "Sign-in is unavailable right now." | :78 |
| Account | Silent failures | GAP: revoke, remove device and end assist swallow errors; failures loading those sections are hidden | :131-141, :257-270, :321-331, :349 |

### Learning

| Screen | State | Shows | Cite |
|---|---|---|---|
| Book `book/[grade]/[subject].tsx` | States | L "Loading chapters"; GAP: no empty message; warn "Part of the supplied textbook file is missing"; a bad grade → `not_found` "Unknown class."; E | :15-19, :32-39, :51 |
| Chapter `chapter/[id].tsx` | States | L "Loading chapter"; "No topics are recorded for this chapter."; warn about a partial chapter | :20, :66-73 |
| Chapter | Offline | E plus "Open the saved copy, if you saved one" | :26-30 |
| Chapter | Access | Pack removed: "Your saved copy was removed: your plan no longer covers this chapter…" | `components/offline-pack.tsx:28-31` |
| Chapter | Update required | A download of a too-new pack shows "This pack needs a newer version of the app." A stored too-new pack **looks absent**. | `offline-pack.tsx:45`; `lib/study-packs.ts:95-97` |
| Topic `topic/[id].tsx` | Loading | L "Loading lesson"; lecture L "Checking for a lecture". **GAP:** a lecture error leaves the spinner forever. | :56, :168; `components/lecture-view.tsx:33,66` |
| Topic | Empty | "This topic's lesson isn't ready yet"; the missing-language note (polite); lecture "coming" | :169-170, :152; `lecture-view.tsx:19-25` |
| Topic | Access | "Included with a plan or the free 30-day trial" / "Start your free trial from the Account tab to read this lesson." (reachable here, unlike the web); lecture-locked wording | :171-172; `lecture-view.tsx:26-32` |
| Topic | Offline | E (no saved-copy link). An offline completion is queued: "Saved on this device. It will be sent when you're back online." An offline note is queued, but **its status line can't show** (it shows "Not saved yet (kept on this device).") | `components/lesson-study.tsx:84-87`, :131-136, :181-192 |
| Topic | Conflict | `NOTE_CHANGED` / `NOTE_DELETED` alert panel with "Keep mine" / "Use the other version" / "Discard mine" | `lesson-study.tsx:19-24`, :138-156 |
| Topic | Update required | Unknown block → fallback, else (`role="alert"`) "This part of the lesson needs a newer version of the app to display." | `components/lesson-blocks.tsx:223-237` |
| Offline copy `offline/[id].tsx` | Missing pack | Warn "No saved copy…". **GAP:** shown also when the app started offline (`unavailable` → no owner), when the pack expired, and when the pack format is too new. | :20-31; `lib/study-packs.ts:95-97` |
| Offline copy | Self-check | "Choose an answer to see the explanation. Nothing here is sent, saved or scored." | :66 |
| Help article `help-article/[slug].tsx` | States | L; "Shown in English"; E (404 → "Go to Learn") | :19-25 |

### Practice and results

| Screen | State | Shows | Cite |
|---|---|---|---|
| Attempt `attempt/[id].tsx` | Loading | L "Checking your sign-in" / "Loading your test" | :45, :56 |
| Attempt | Signed out | A bare Notice "Sign in to continue" with no container or button (also shown for `unavailable`). Load 401 → `handleError`. 401/403 during a save → offline retry loop (§3.3). | :46, :53-55, :169-174 |
| Attempt | Conflict | `ATTEMPT_ELSEWHERE`; other 409 → apply `problem.results` and reload; `MOCK_IN_PROGRESS` → `MockRunningNotice` | :21-22, :157-168, :58-59 |
| Attempt | Submitted | "Time is up" / "Submitted", "{a} of {q} answered · receipt {8}", "See your result" | :63-80 |
| Attempt | Answer states | Section 3 | — |
| Result `result/[id].tsx` | Pending | `RESULTS_PENDING` "Your answers are saved"; `SCORING_PENDING` "Submitted: your result is being prepared" (no refresh) | :38-48 |
| Result | Not scorable | "This test can't be scored…" | :58-61 |
| Result | Score revised | "Updated {date}" with "{reason} Your earlier result stays in your history."; badges Excluded / Credited / Key corrected; "Some last changes weren't counted"; **no score-history list** (the web has one) | :70-74, :78-85, :128-129 |
| Result | Conflict | `MOCK_IN_PROGRESS` → notice | :50-51 |
| Mocks `mocks.tsx` | States | L "Loading test patterns"; "No mock tests yet…"; SO "Sign in to take a mock" | :25, :78-82 |
| Mocks | Failure | GAP: a failed sessions request is hidden. A start 401 shows `FormError` (the condition is inverted, so `handleError` is never called). `MOCK_IN_PROGRESS` / `ENTRY_CLOSED` → message only. | :45-47, :56 |
| Notebook `notebook.tsx` | States | L; "Nothing here yet…"; SO; `MOCK_IN_PROGRESS` → notice; a review 401 → `FormError` (inverted) | :24, :34-41, :53-55 |
| Dashboard `dashboard.tsx` + `components/dashboard.tsx` | States | SO "Sign in to see your dashboard" (also shown while auth is loading); L "Loading your dashboard"; "Choose your class and subjects…"; meters "Unavailable. {reason}" | `app/dashboard.tsx:18`; comp :25-34, :83-95 |
| Dashboard | Score revised | GAP: no revised marker; a not-scorable row is labelled "Result: {raw} of {max}" | comp :101-108 |
| Evidence `evidence.tsx` | States | L "Working out your evidence"; "No topics yet"; meter "Unavailable"; "Not enough evidence yet"; SO | :18, :37-45, :52-67 |
| Plan `plan.tsx` | States | L "Planning"; "This fits your time" / "About {x} short"; the button is disabled outside 10-600 minutes or for a bad date (no message); a 422 → "Something went wrong" | :31, :44-46, :56-70 |
| Progress `progress.tsx` | States | L "Preparing your report"; "No submitted tests yet"; "Results on the way"; SO | :21, :28-46 |
| Study `study.tsx` | States | L; three empty texts; warn "The lesson has been updated"; any of the three requests failing fails the whole screen; formula removal errors swallowed | :29-36, :45-100 |

### Account-adjacent

| Screen | State | Shows | Cite |
|---|---|---|---|
| Onboarding `onboarding.tsx` | States | "Sign in first" with "Go to Account" (also for `unavailable`); "Choose your class."; 422 → "Please check: {field}: {msg}"; offline → message in `FormError` | :50-58, :77, :93-101 |
| Notifications `notifications.tsx` | States | L; "Nothing yet…"; "{n} unread"; a revised-score link opens the result; mark-read errors swallowed; an unknown link stays on the screen silently | :19-27, :35-67 |
| Settings `settings.tsx` | States | L "Loading your usual settings"; every save error → "Couldn't save your settings. Check your connection and try again."; "Saved as your usual settings." (polite) | :143-153, :185 |
| Help `help.tsx` | States | L; "No requests yet."; "No matching articles."; Send disabled until subject ≥ 3 and body ≥ 5 characters (no hint); "Sent. We'll reply here." (not live); screenshot type and size errors | :39-40, :69, :85-94, :126, :140, :187-189; `lib/screenshots.ts:9-10` |

### Written (mobile)

| Screen | State | Shows | Cite |
|---|---|---|---|
| `written/[id].tsx` | Loading | L "Checking your sign-in" / "Loading your written test"; result L "Loading your marks" | :36, :43; `components/written-result.tsx:66` |
| `written/[id].tsx` | Signed out | A bare "Sign in to continue". A load 401 is not passed to `handleError`. | :37, :41-47 |
| `written/[id].tsx` | Conflict | Mapping 409: "Your mapping changed on another device. The latest version has been loaded." (the reload inside the catch is unguarded) | :146-148 |
| `written/[id].tsx` | Other | Section 6 | — |
| `written/linked/[formId].tsx` | States | L; "Sign in to continue"; warn "Not enough allowance"; "Already started" with "Open it"; start failure "The test couldn't be started. Nothing was charged; try again later." | :18-19, :27-39, :51-55, :74-76 |

---

## 6. Written-answer states (web and mobile)

The roadmap's five answer states are defined for MCQ answers. For written scripts the code keeps a separate, explicit
lifecycle. This table lists the labels each client uses for each lifecycle stage.

| Stage | Web (`app/practice/written/[id]/written-runner.tsx` unless noted) | Mobile (`app/written/[id].tsx`, `lib/written-pages.ts`, `components/written-result.tsx`) |
|---|---|---|
| Active | "Stop writing at", "Upload and submit by … (m:ss left)"; refreshes itself at the cutoff (:358-374, :134-136) | Notice "Not submitted yet": "…Uploaded pages are not marked until you submit." (:209-214) |
| Chosen, not sent | The file is held in memory only, so a reload loses it (:92) | "On this phone, not sent yet": "{name}: sending…" / "{name}: not sent — {error}" · "kept on this phone" or "not kept on this phone"; "Send again", "Remove". Re-sent automatically once, when the screen opens (:284-302, :95-100) |
| Uploading | `<progress aria-label="Uploading {name}">` inside an `li role="status"` (:579-583) | "sending…" (:284-302) |
| Upload failed | The API detail, or "Connection lost. Your file is kept on this device: try again.", or "Upload failed ({status})."; "Try {name} again" (status 0 or ≥ 500), "Remove from this list", "What can I upload?" (:156, :585-599) | "not sent — {error}". The row is `role="alert"`. Fallback text: "That didn't upload. Check your connection." (`lib/written-pages.ts:157`) |
| Rejected file | No separate state: API refusals appear as non-retryable failed uploads; duplicates say "{file} was already uploaded." (:149, :610-616) | Capture notice (`role="alert"`, **never cleared**): unsupported type, file too large, "couldn't be kept on your phone…" (:265-269; `lib/written-pages.ts:112-127`) |
| Uploaded | "Page N · uploaded, not yet submitted" (:534) | The same, but the label reads **"submitted" while sealing** (:314, :502) |
| Scan quality | Warnings plus "These are automatic checks, not a judgement…" (:566-576, :604-609) | The same (:322-333) |
| Map save | "Saving…" / "Saved · revision N"; on conflict, "Load the latest mapping" (:625-633) | "Saving…" / "Saved · revision N · X of Y parts mapped" (:406-408) |
| Submit blocked | "Give every part at least one page…", "Mark the answers' areas or confirm…" (:704-712) | "Wait until your pages have finished uploading and saving.", "N page(s) … on this phone but not sent…", "Every part needs a page or "I didn't answer this".", "Confirm the question numbers…" (`lib/written-pages.ts:90-100`) |
| Sealed | Ok "Submitted for marking" with the receipt and counts (:339-344) | "Submitted for marking" / "Receipt {8} · …" (:192-197) |
| Expired | Warn "The upload window closed before you submitted" with a help link (:352-357) | Warn "Upload window closed… Its allowance was returned." (:204-208) |
| Marks pending | "Waiting for a teacher" (:391); work status lines (:765-773) | "Waiting for a teacher" [+ "Marking is taking longer than planned; nothing has been lost."] (`written-result.tsx:69-75`) |
| Marks partial or unavailable | "Marking isn't finished yet" / "Some questions couldn't be assessed", with Marked / Still being marked / Couldn't be assessed / Whole test lines; per question "pending" / "couldn't be assessed" plus the reason and allowance returned; "No mark for this test" (:405-437, :725-762) | The same set (`written-result.tsx:37-54`, :87-92, :118-132) |
| Learner action needed | Rescan or confirm blank: "Please act by {deadline}", "Send a clearer copy", "I didn't answer this question", "This copy was already received…" (`pending-action.tsx:69-121`) | Warn "Action for question N", "Send a clearer photo", "I didn't answer this question" (`written-result.tsx:215-286`) |
| Score revised | "Marking guide corrected"; "waiting to be re-marked under a corrected marking guide" / "carried forward unchanged…"; "Mark history" (:398-418; `recheck-panel.tsx:37-66`) | Mark history, notices and regrade text (`written-result.tsx:97-112`, :176-208) |
| Recheck | "Recheck requested", window closed, or the form; the 10-character minimum is not stated (`recheck-panel.tsx:67-158`) | The same. Uses radio semantics for a multi-select, and the minimum is not stated (`written-result.tsx:347-390`) |

---

## 7. Staff and admin routes (summary)

**Authorisation.**
- `requireStaff` (`lib/studio.ts:17-22`) redirects signed-out users. A signed-in user without a content role gets `StudioForbiddenError`, rendered as "Staff only" with "The content studio is for staff with a content role."
- Admin pages call `currentUser()` and render a warn Notice when the API returns 403 ("Not available to you", "Multi-factor sign-in needed", "Finance staff only" and so on).
- `audit`, `catalogue` and `exam-profiles` also check the role in the web app. `studio/assets`, `studio/lectures` and `studio/lectures/[id]` do not; the API still refuses the request.

**Loading.** Every staff page has a labelled `Suspense` fallback, for example "Loading the work queue" (`app/studio/page.tsx:94`) and "Loading staff" (`app/admin/staff/page.tsx:27`).

**Errors.**
- Most staff pages show failures inline as a warn Notice (`role="note"`).
- The studio queue (`lib/studio.ts:40`), `getItem` (`:54`) and `studio/new` catalogue loading throw to the learner-worded `app/error.tsx`.
- Several pages turn any failed load into a permission message: academic-reviews :56, adjudications :38, calibration :75, marking :37, reviewer-quality :50.
- Several call `notFound()` for any failure: adjudications/[id] :45-47, concepts/[id] :43, support/[id] :45-47, support/learners/[id] :72.
- `admin/service` hides a failing panel by returning `null` (:115, :166, :230, :277, :334).

**Empty states.** Present on most list pages. GAP on catalogue, economics, exam-profiles preview, learning, studio/help, studio/new, studio/sources (sources list) and support/learners/[id].

**Conflict.**
- `studio/items/[id]` is the only full implementation. The revision is sent with each save, and a 409 opens `ConflictPanel` (`role="alert"`) "Someone else saved a newer version", offering "Use their version (discard mine)" or "Save mine on top of theirs". Autosave stops while the conflict is open, unsaved work is recovered from the browser, and there is a `beforeunload` guard (`app/studio/items/[id]/workspace.tsx:197`, :224, :258, :402-450).
- Marking sends `expected_version` and offers "Reload the latest version" (`app/actions/marking.ts:52`; `marking-workspace.tsx:202-206`).
- Lecture master uploads resume on `UPLOAD_OFFSET` (`studio/lectures/[id]/detail-forms.tsx:119`).
- Exam-profile drafts, search terms, staffing and other admin forms send no revision, so the last write wins. No page uses `If-Match` or `ETag`.

**Update required.** Staff can raise or lower a platform's minimum app version (`app/admin/service/client-minimum-form.tsx`). The service page lists registered builds and their renderer versions (`app/admin/service/page.tsx:309`).

**Score revised.**
- Corrections are created at `studio/adjudications/new`.
- Regrade jobs run from `studio/adjudications/[id]`, where `RunRegrade` reports progress with `role="status"` / `role="alert"` (`run-regrade.tsx:62,69`) and superseded corrections are labelled (:114).

---

## 8. Prioritised gaps

Priority 1: a learner is misinformed or can lose work. Priority 2: the state is missing or has no next action.
Priority 3: the state is incomplete or inconsistent.

| # | P | Gap | Where |
|---|---|---|---|
| G1 | 1 | Web topic reader tells learners without a plan that a published lesson "isn't ready yet… has not been published". The locked notice and the lecture-locked notice are unreachable. | `app/learn/topic/[topicId]/page.tsx:85,166-174`; API `modules/content/reading.py:185` |
| G2 | 1 | Mobile started offline: auth `unavailable` is shown as signed out on about 15 screens, and the saved offline copy reads "No saved copy". Offline reading, unsent answers and pages are unreachable until the connection returns. | `lib/auth.tsx:53-56`; `app/offline/[id].tsx:20-31`; e.g. `app/attempt/[id].tsx:46` |
| G3 | 1 | Mobile sign-out deletes unsent answers, page drafts and queued notes without warning. | `lib/auth.tsx:82-88`; `app/(tabs)/account.tsx:241` |
| G4 | 1 | Session expiry or access ending during a test (401/403 on save) is labelled "Offline" and retried forever, with no sign-in or plan path. | web `app/actions/practice.ts:123` + `attempt-runner.tsx:161-167`; mobile `app/attempt/[id].tsx:169-174` |
| G5 | 1 | Technical failures are shown as content states. As "not found": web topic, help ticket, help article, linked written test. As "empty": help list, mock sessions. As "pending": written result → "Waiting for a teacher". As "coming": lecture. Sign-in shows "not available in this environment". Mobile collapses 403/426/429/503 into "Something went wrong". | §4, §5; mobile `lib/api.ts:207-210` |
| G6 | 1 | The runner summary line says "all saved" while answers are rejected, and "Saving n…" while answers are only selected or held. | web `attempt-runner.tsx:298-299,341-347`; mobile `app/attempt/[id].tsx:289-290,342-344` |
| G7 | 2 | Answer states rely on colour in the palette. Mobile uses the same colour for `saved` and `selected`, and for `saving` and `pending`. There are no icons, state changes are not announced, and the mobile current question is not exposed. | web `attempt-runner.tsx:20-27`; mobile `app/attempt/[id].tsx:355` |
| G8 | 2 | §5.4 rule 5: attempt start is not blocked for forms containing an item this client can't render. Mobile 426 never reaches `VersionGate`. A too-new pack looks absent. The web notice tells website users to update "the app". | `components/lesson-blocks.tsx:238-245`; mobile `lib/api.ts:207`, `lib/study-packs.ts:95-97` |
| G9 | 2 | §5.7: there is no correction notice during an active attempt. Dashboards (web and mobile) don't mark revised scores. Mobile results have no score history. | `attempt-runner.tsx`; `components/dashboard.tsx:201-207`; mobile `components/dashboard.tsx:101-108` |
| G10 | 2 | Web server actions outside the two runners reject to `error.tsx` when offline: the page and typed input are lost. Two calls run outside a transition and leave `busy` stuck. | `lib/reach.ts`; `pending-action.tsx:30-36`; `components/study-settings.tsx:46-65` |
| G11 | 2 | Silent mutation failures. Web: mark completed, remove formula, remove trial device, revoke sessions, cancel or retry export, notifications, notebook note, favourite, check answer. Mobile: account actions, mark read, formula removal, check answer, continue-here (invisible). | §4, §5 |
| G12 | 2 | Mobile reads have no timeout (spinner forever). A lecture load error spins forever. The lecture "coming" notice promises lesson text that the Lecture view doesn't show. | `lib/api.ts:194`; `app/topic/[id].tsx:168`; `components/lecture-view.tsx:22` |
| G13 | 2 | Access-expired copy: an ended trial is told to "Start your free trial or sign in". The ended/no-plan `PlanStatus` has no link. The web dashboard has no plan notice. A guest's return path is lost via `/account`. | `app/learn/chapter/[chapterId]/page.tsx:222-231`; `components/plan-status.tsx:60-64` |
| G14 | 2 | `MOCK_IN_PROGRESS` gets "Back to your mock" only on some routes. The practice builder, start and join mock, and notebook review show bare text (web and mobile). | `practice-builder.tsx:212-217`; `start-mock.tsx:32-36`; mobile `(tabs)/practice.tsx:129-133` |
| G15 | 3 | 404 and 410 (retired) are never told apart; one generic not-found message. | `app/not-found.tsx`; mobile `lib/api.ts:205` |
| G16 | 3 | Missing empty states: book with no chapters, `/learn` with all books empty, plan schedule, evidence outcomes, several staff lists. | §4, §7 |
| G17 | 3 | Mobile progress queue: queued ops aren't flushed after `enqueue`. A non-temporary error drops an op silently. The offline note status line is unreachable. | `lib/progress-queue.ts:45-48`; `lib/progress-queue-core.ts:43-46`; `components/lesson-study.tsx:131-136` |
| G18 | 3 | Written: on the web a failed upload is held in memory only and lost on reload. On mobile the capture notice is never cleared, and pages read "submitted" while sealing. | `written-runner.tsx:92`; mobile `lib/written-pages.ts:112-127`, `app/written/[id].tsx:314,502` |
| G19 | 3 | Staff error states use learner copy (`error.tsx`, `not-found.tsx`). Several staff pages turn any failure into a permission message or `notFound()`. Conflicts are handled only for studio items and marking. | §7 |
| G20 | 3 | `SCORING_PENDING` and `RESULTS_PENDING` result pages never refresh and offer no refresh button (web and mobile). | `result/page.tsx:50-55`; mobile `app/result/[id].tsx:38-48` |
