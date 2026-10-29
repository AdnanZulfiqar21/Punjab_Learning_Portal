import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { FavouriteTopic, SavedFormula, StudyNoteListed } from "@portal/contracts";
import { removeFormula } from "@/app/actions/study";
import { GlassCard } from "@/components/glass-card";
import { Icon, type IconName } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api, currentUser, features } from "@/lib/session";
import { TIME_ZONE } from "@/lib/dates";

export const metadata: Metadata = { title: "My study tools", robots: { index: false } };

const subject = (s: string) => s.replace("_", " ");
const day = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE }) : "");

const LINK = "font-medium text-accent underline underline-offset-2";

/** A section's heading with its icon (DESIGN-01). */
function ToolHeading({ id, icon, children }: { id: string; icon: IconName; children: string }) {
  return (
    <h2 id={id} className="flex items-center gap-2.5 font-display text-2xl font-semibold tracking-tight">
      <span aria-hidden className="grid size-9 place-items-center rounded-inner bg-accent-soft text-accent">
        <Icon name={icon} size={18} />
      </span>
      {children}
    </h2>
  );
}

/** P11.S2.T2 (STUDY-TOOLS-01): everything a learner kept, in one private place. DESIGN-01: a glass hero and cards. */
export default function StudyPage() {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/", label: "Dashboard" }, { label: "My study tools" }]} />
        <PageHero
          align="start"
          eyebrow="Private to you"
          title="My study tools"
          lead="Your notes, favourite topics and saved formulas. Only you can see them."
          backdrop={<span aria-hidden className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading your study tools" />}>
        <Tools />
      </Suspense>
    </div>
  );
}

async function Tools() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/study");
  if ((await features(user.token)).study_tools !== true) {
    return <Notice title="Not available on your account yet">Study tools are being introduced gradually. Please check again later.</Notice>;
  }
  const [notes, favs, formulas] = await Promise.all([
    api<StudyNoteListed[]>("/v1/me/notes", { token: user.token }),
    api<FavouriteTopic[]>("/v1/me/favourites", { token: user.token }),
    api<SavedFormula[]>("/v1/me/formulas", { token: user.token }),
  ]);
  if (!notes.ok || !favs.ok || !formulas.ok) {
    return <Notice tone="warn" title="Couldn't load your study tools">Please try again.</Notice>;
  }
  return (
    <div className="space-y-10">
      <section aria-labelledby="notes-h" className="space-y-3">
        <ToolHeading id="notes-h" icon="file-text">
          Notes
        </ToolHeading>
        {notes.data.length === 0 ? (
          <p className="text-sm text-muted">No notes yet. Add a private note under any lesson you can read.</p>
        ) : (
          <GlassCard as="div" padded={false} className="overflow-hidden">
          <ul className="divide-y divide-border text-sm">
            {notes.data.map((n) => (
              <li key={n.lesson_id} className="space-y-1.5 px-5 py-4">
                <Link href={`/learn/chapter/${n.chapter_id}#lesson-${n.lesson_id}`} className={LINK}>
                  {n.lesson_title}
                </Link>
                <span className="text-muted">
                  {" "}
                  · {GRADE_LABEL[n.grade]} <span className="capitalize">{subject(n.subject)}</span> · Chapter {n.chapter_number} · {day(n.updated_at)}
                </span>
                <p className="rounded-inner bg-surface px-3 py-2 whitespace-pre-wrap">{n.text}</p>
              </li>
            ))}
          </ul>
          </GlassCard>
        )}
      </section>

      <section aria-labelledby="favs-h" className="space-y-3">
        <ToolHeading id="favs-h" icon="list-checks">
          Favourite topics
        </ToolHeading>
        {favs.data.length === 0 ? (
          <p className="text-sm text-muted">No favourites yet. Star a topic in any chapter&apos;s topic list.</p>
        ) : (
          <GlassCard as="div" padded={false} className="overflow-hidden">
          <ul className="divide-y divide-border text-sm">
            {favs.data.map((f) => (
              <li key={f.topic_id} className="px-5 py-3.5">
                <Link href={`/learn/chapter/${f.chapter_id}`} className={LINK}>
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
          </GlassCard>
        )}
      </section>

      <section aria-labelledby="formulas-h" className="space-y-3">
        <ToolHeading id="formulas-h" icon="layers">
          Saved formulas
        </ToolHeading>
        {formulas.data.length === 0 ? (
          <p className="text-sm text-muted">No formulas yet. Use &quot;Save formula&quot; under a formula in a lesson.</p>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2">
            {formulas.data.map((f) => (
              <GlassCard as="li" key={f.id} className="flex flex-col gap-3 text-sm">
                <div className="space-y-1 rounded-inner border border-border bg-surface px-4 py-3">
                  <p className="text-base">{f.text_alt}</p>
                  <p className="font-mono text-xs text-muted">{f.latex}</p>
                </div>
                {f.updated_since && (
                  <p className="rounded-inner border border-warn bg-warn-soft px-3 py-2">
                    This lesson has been updated since you saved this formula. Check the lesson for the current version.
                  </p>
                )}
                <div className="mt-auto flex flex-wrap items-center justify-between gap-2">
                  <Link href={`/learn/chapter/${f.chapter_id}#lesson-${f.lesson_id}`} className={LINK}>
                    {f.lesson_title}
                  </Link>
                  <form action={removeFormula.bind(null, f.id)}>
                    <button type="submit" className="inline-flex min-h-11 items-center rounded-full px-3 font-medium text-muted underline-offset-2 hover:bg-danger-soft hover:text-danger hover:underline">
                      Remove
                    </button>
                  </form>
                </div>
              </GlassCard>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
