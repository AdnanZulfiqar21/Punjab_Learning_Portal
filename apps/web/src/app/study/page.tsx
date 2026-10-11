import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { FavouriteTopic, SavedFormula, StudyNoteListed } from "@portal/contracts";
import { removeFormula } from "@/app/actions/study";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "My study tools", robots: { index: false } };

const subject = (s: string) => s.replace("_", " ");
const day = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium" }) : "");

/** P11.S2.T2 (STUDY-TOOLS-01): everything a learner kept, in one private place. */
export default function StudyPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/", label: "Dashboard" }, { label: "My study tools" }]} />
      <h1 className="text-2xl font-semibold tracking-tight">My study tools</h1>
      <p className="text-sm text-muted">Your notes, favourite topics and saved formulas. Only you can see them.</p>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading your study tools" />}>
        <Tools />
      </Suspense>
    </div>
  );
}

async function Tools() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/study");
  const [notes, favs, formulas] = await Promise.all([
    api<StudyNoteListed[]>("/v1/me/notes", { token: user.token }),
    api<FavouriteTopic[]>("/v1/me/favourites", { token: user.token }),
    api<SavedFormula[]>("/v1/me/formulas", { token: user.token }),
  ]);
  if (!notes.ok || !favs.ok || !formulas.ok) {
    return <Notice tone="warn" title="Couldn't load your study tools">Please try again.</Notice>;
  }
  return (
    <div className="space-y-8">
      <section aria-labelledby="notes-h" className="space-y-2">
        <h2 id="notes-h" className="text-lg font-semibold">
          Notes
        </h2>
        {notes.data.length === 0 ? (
          <p className="text-sm text-muted">No notes yet. Add a private note under any lesson you can read.</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {notes.data.map((n) => (
              <li key={n.lesson_id} className="space-y-1 px-4 py-3">
                <Link href={`/learn/chapter/${n.chapter_id}#lesson-${n.lesson_id}`} className="font-medium text-accent underline underline-offset-2">
                  {n.lesson_title}
                </Link>
                <span className="text-muted">
                  {" "}
                  · {GRADE_LABEL[n.grade]} <span className="capitalize">{subject(n.subject)}</span> · Chapter {n.chapter_number} · {day(n.updated_at)}
                </span>
                <p className="whitespace-pre-wrap">{n.text}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="favs-h" className="space-y-2">
        <h2 id="favs-h" className="text-lg font-semibold">
          Favourite topics
        </h2>
        {favs.data.length === 0 ? (
          <p className="text-sm text-muted">No favourites yet. Star a topic in any chapter&apos;s topic list.</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {favs.data.map((f) => (
              <li key={f.topic_id} className="px-4 py-3">
                <Link href={`/learn/chapter/${f.chapter_id}`} className="text-accent underline underline-offset-2">
                  {f.number ? `${f.number} ` : ""}
                  {f.title}
                </Link>
                <span className="text-muted">
                  {" "}
                  · {GRADE_LABEL[f.grade]} <span className="capitalize">{subject(f.subject)}</span> · Chapter {f.chapter_number}: {f.chapter_title}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="formulas-h" className="space-y-2">
        <h2 id="formulas-h" className="text-lg font-semibold">
          Saved formulas
        </h2>
        {formulas.data.length === 0 ? (
          <p className="text-sm text-muted">No formulas yet. Use &quot;Save formula&quot; under a formula in a lesson.</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {formulas.data.map((f) => (
              <li key={f.id} className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
                <p className="text-base">{f.text_alt}</p>
                <p className="font-mono text-xs text-muted">{f.latex}</p>
                {f.updated_since && (
                  <p className="rounded-lg border border-warn bg-warn-soft px-2 py-1">
                    This lesson has been updated since you saved this formula. Check the lesson for the current version.
                  </p>
                )}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Link href={`/learn/chapter/${f.chapter_id}#lesson-${f.lesson_id}`} className="text-accent underline underline-offset-2">
                    {f.lesson_title}
                  </Link>
                  <form action={removeFormula.bind(null, f.id)}>
                    <button type="submit" className="text-muted underline-offset-2 hover:text-danger hover:underline">
                      Remove
                    </button>
                  </form>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
