import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { BookExercises } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { exerciseStatus } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { SUBJECTS as ALL_SUBJECTS } from "@/lib/practice";

// The book exercises cover the textbooks the portal teaches; Mathematics is not taught (owner, 2026-10-19).
const SUBJECTS = ALL_SUBJECTS.filter(([code]) => code !== "mathematics");
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Book exercises", robots: { index: false } };

/** BOOK-EXERCISES-01: each chapter's end-of-chapter exercise from the textbook, solved here rather than in Learn. */
export default function BookExercisesPage({ searchParams }: PageProps<"/practice/exercises">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Book exercises" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Book exercises</h1>
        <p className="text-muted">The exercise at the end of each chapter of your textbook, solved in English and Roman Urdu.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading book exercises" />}>
        {searchParams.then((sp) => (
          <Exercises grade={typeof sp.grade === "string" ? sp.grade : undefined} subject={typeof sp.subject === "string" ? sp.subject : undefined} />
        ))}
      </Suspense>
    </div>
  );
}

async function Exercises({ grade: rawGrade, subject: rawSubject }: { grade?: string; subject?: string }) {
  const user = await currentUser();
  const profile = user?.me.profile;
  const grade = rawGrade === "11" || rawGrade === "12" ? Number(rawGrade) : (profile?.grade ?? 11);
  const subject = SUBJECTS.some(([c]) => c === rawSubject) ? rawSubject! : (profile?.subjects?.find((s) => SUBJECTS.some(([c]) => c === s)) ?? "computer_science");
  const res = await api<BookExercises>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/exercises`, user ? { token: user.token } : {});
  const name = SUBJECTS.find(([c]) => c === subject)?.[1];
  return (
    <div className="space-y-6">
      <nav aria-label="Choose class and subject" className="flex flex-wrap gap-2">
        {[11, 12].map((g) =>
          SUBJECTS.map(([code, label]) => {
            const active = g === grade && code === subject;
            return (
              <Link
                key={`${g}-${code}`}
                href={`/practice/exercises?grade=${g}&subject=${code}`}
                aria-current={active ? "page" : undefined}
                className={`rounded-full border px-3 py-1.5 text-sm ${active ? "border-accent bg-accent-soft font-medium text-accent" : "border-border bg-surface hover:border-accent"}`}
              >
                {GRADE_LABEL[g]} {label}
              </Link>
            );
          }),
        )}
      </nav>
      {!res.ok ? (
        <Notice tone="warn" title="Couldn't load the book exercises">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      ) : res.data.exercises.length === 0 ? (
        <Notice title="No book exercises here yet">
          The end-of-chapter exercises of the {GRADE_LABEL[grade]} {name} book are added chapter by chapter. They appear here once they are.
        </Notice>
      ) : (
        <ol className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {res.data.exercises.map((e) => {
            const status = exerciseStatus(e.availability, e.available_languages);
            const label = (
              <>
                <span className="w-24 shrink-0 text-sm font-semibold">
                  {res.data.chapter_label} {e.chapter_number}
                </span>
                <span className="min-w-0 flex-1 font-medium">{e.chapter_title}</span>
                <Badge tone={e.availability === "published" ? "ok" : e.availability === "private_preview" ? "info" : "warn"}>{status.label}</Badge>
              </>
            );
            return (
              <li key={e.topic_id}>
                {status.open ? (
                  <Link href={`/practice/exercises/${e.topic_id}`} className="flex flex-wrap items-center gap-3 px-4 py-3 hover:text-accent">
                    {label}
                  </Link>
                ) : (
                  <div className="flex flex-wrap items-center gap-3 px-4 py-3 text-muted">{label}</div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
