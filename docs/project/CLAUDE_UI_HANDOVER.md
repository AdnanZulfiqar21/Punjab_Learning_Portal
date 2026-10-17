# Claude UI handover

**17 October 2026.** Cursor branch `feat/topic-reader` at `c9028c7` (local worktree `C:\Users\Lenovo T14\AppData\Local\Temp\plp-reader`). Do not edit that worktree at the same time. Visual styling stays on a separate branch.

## What the iPhone is doing

Installed build **0.1.0 (2)**, commit `c9028c7`, bundle `pk.punjablearningportal.student.preview`, no over-the-air updates. API origin baked in: `http://172.20.10.2:8100`. Settings shows variant, build, source and that origin. It shows no token.

The 1:21 screenshots are this build. “This lesson is not ready yet” is the `unavailable` response, not a missing route. Checked again on 17 October: anonymous `GET /v1/topics/255b5a9d-355f-56ca-adb6-10fc6d2825fb/lesson` returns `unavailable` and no body. `studio-author@example.com` receives `private_preview` with 29 blocks. The draft is not published.

## Contracts Claude can rely on

- Chapter screen lists topics. The title navigates to `/topic/[id]`. **Outline** is a separate control. No PDF-page badges and no source-id panel.
- `GET /v1/topics/{topic_id}/lesson` returns `availability`: `published`, `private_preview`, or `unavailable`. `lesson` is null when unavailable. Draft text is only on `private_preview`.
- Lesson blocks in use: `heading`, `paragraph`, `list`, `callout`, `table`, `checkpoint`, `scene`. `scene` is currently only `bacterial_shapes`, with alt text and a caption. Unknown block types must keep the existing fallback line.
- Previous and next topic ids are on the same response. Reading position is saved only for a published lesson the learner can read. Opening a draft does not write progress.

## Files with functional layout, not a theme

- `apps/mobile/src/app/chapter/[id].tsx`
- `apps/mobile/src/app/topic/[id].tsx`
- `apps/mobile/src/components/lesson-blocks.tsx`
- `apps/web/src/app/learn/chapter/[chapterId]/page.tsx`
- `apps/web/src/app/learn/topic/[topicId]/page.tsx`
- `apps/web/src/components/lesson-blocks.tsx`

Biology XI Chapter 1 coverage: topic 1.1 is a private draft. Topics 1.2–1.8 have no lesson row. Nothing in the chapter is published or academically reviewed.
