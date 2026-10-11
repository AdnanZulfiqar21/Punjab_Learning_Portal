# Lecture production register

This register tracks the **premium animated lectures** for Class XI and Class XII: media production, not platform
code. Platform engineering is tracked separately in `docs/project/` (IMPLEMENTATION_REGISTER, DECISIONS). The portal
keeps the authoritative per-lecture record (Studio → Lectures, `/v1/studio/lectures`, LECTURE-01). This file is the
owner-facing summary and the place to record decisions made outside the portal.

**Nothing listed here is academically approved unless the portal shows an approving independent review**, with every
check passed and the reviewer's notes. Producing, uploading or generating a video never approves it.

## Where things live

| Material | Where | Committed to git? |
|---|---|---|
| Owner's working media (videos, narration audio, project files) | `Animated Lectures/` on the owner's machine | **Never** (git-ignored; the repository is public) |
| Storyboard: scenes, narration, claims with textbook page references | Portal content item of kind `storyboard` (reviewed and published) | Only as database records |
| Master video | Owner archive; registered in the portal by file name, SHA-256, size, duration and location | No (file); yes (checksum record) |
| Captions (WebVTT) per language | Portal asset archive (kind `caption`), same class and subject | Database and private storage |
| Transcript (one entry per storyboard scene) | Portal lecture record, editable until review | Database |
| Narration voices | Portal voice registry (`/v1/studio/voices`) | Database |

## Workflow

1. **Storyboard.** Write and review it in the studio. Every factual claim cites a textbook page from that class's
   book (Class XI and XII are never mixed). Publication needs confirmed source rights.
2. **Voice.** Propose the narration voice (language: Roman Urdu, Urdu or English; production tool; the tool's voice
   reference). The **owner approves it** in the portal (MFA, with evidence such as "listened to the sample, chosen
   for all Class XI Biology lectures"). Keep one approved voice per language and series for consistency. A retired
   voice can't start new lectures.
3. **Produce** the animation and narration outside the portal from the published storyboard. The storyboard's prompt
   package (`/prompt-package`) records the teaching constraints separately from creative direction.
4. **Register** the lecture in the portal: pick the published storyboard version, the narration language and the
   approved voice. Then register the master (SHA-256 and size), edit the transcript per scene, and attach reviewed
   WebVTT captions from the asset archive.
5. **Review.** An independent subject reviewer for that class and subject, never someone who produced the lecture,
   checks: accuracy, voice/text alignment, pacing, spelling, diagrams, captions, rights and **textbook-source
   verification**. They note scientific terms, Roman Urdu spellings, pronunciation and equation descriptions. Approval
   needs every check. "Request changes" sends it back.
6. **Release** to learners needs the media provider (BLOCKERS B05). Until then an approved lecture is a reviewed,
   frozen production record only.

## Roman Urdu narration and subtitles

- Use one consistent Roman Urdu spelling for each scientific term across a series. Record agreed spellings in the
  reviewer's notes. A shared glossary is part of the AI production evaluation contract (P07.S4.T4), which waits on
  reviewers (B01).
- Keep English technical terms where the textbook uses them, and say them the same way each time.
- Captions are timed WebVTT, matching the narration. Equations get a spoken description in the transcript.

## Lectures

| Class | Subject | Chapter | Storyboard | Voice | Master SHA-256 | Captions | Portal status | Academically approved |
|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | **None yet** |

*2026-10-11:* the owner's `Animated Lectures/Class 11 Videos` folder exists locally (825 MB). It has **not** been
registered, reviewed or approved, and it is not committed. Register each video against its reviewed storyboard to
start its record.
