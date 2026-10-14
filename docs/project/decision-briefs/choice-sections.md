# Decision brief: choice sections in written tests (WA-D03, WA-D15)

Prepared 2026-10-14 for the PR #188 review (gap 6). **Not a decision.** Nothing here is live: today's forms offer no
optional answers (WA-D03 interim default) and no composite board papers (WA-D15). An owner and academic-lead approval,
recorded in DECISIONS with its date and approver, is what unlocks the work below.

## What needs deciding

Some papers say "attempt any N of M". When a learner answers more than N, or fewer, someone has to decide which
answers count. Roadmap §20.7.1 and acceptance criterion WA-AC08 set the limits:

- The approved policy explicitly selects which answers count. Never quietly pick the best N.
- Answering fewer doesn't lower the maximum. An unanswered required slot scores zero within the fixed maximum.
- Extra answers are kept as unscored evidence.
- Choices worth different marks need a source-approved, deterministic denominator and allowance reservation. A form
  that doesn't fit is refused before it starts.

## Options

| Option | How counted answers are chosen | For | Against |
|---|---|---|---|
| **A. The learner chooses (recommended default)** | Before submitting, the learner marks which N answers count; the others are kept unscored. Submitting is refused until exactly N are chosen, or fewer with the rest marked not answered. | Explicit, as the roadmap asks ("confirm counted answers explicitly"); nothing to dispute later; works on web and mobile | One more step for the learner |
| B. The first N in question order | The lowest-numbered N answered questions count. | Matches common board instructions | Must be source-verified for Punjab Class XI/XII papers (B02); learners may not expect it |
| C. The first N as written (page order) | The first N answers on the pages, as mapped, count. | Mirrors a paper script | Depends on the learner's page mapping, so it is easy to get wrong |

Not offered, because the roadmap rules them out: picking the best N automatically, or lowering the maximum.

**Recommendation:** A for practice tests. B only for composite board papers (WA-D15), and only where the board's
instruction for that paper is source-verified (B02).

## What it unlocks

- W04.S1.T2: section-choice rules, and counted versus extra answers.
- W04.S1.T3: the "maximum weighted choice reservation" in the start terms.
- WA-D15: composite board papers, together with source-verified timing, maxima, corrections and release (B02).

## Acceptance tests to add once decided (from WA-AC08 and §20.7.1)

1. A choose-2-of-3 section with three answers: under A, the learner's two choices are scored and the third is stored
   as unscored evidence that markers can see.
2. The same section with one answer: the maximum is unchanged, and the missing slot scores 0 with a reason.
3. Submitting with no counted answers chosen (A) is refused with a clear reason, on web and mobile (the mobile gate
   in `lib/written-pages.ts` gains this check).
4. A form whose choices carry different marks with no approved denominator is refused at publication and at start.
5. A regrade or rubric correction never changes which answers counted.
6. Results and exports show which answers counted and why.
