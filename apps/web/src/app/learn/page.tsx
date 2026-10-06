import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { getCatalogue } from "@/lib/api";
import { GRADE_LABEL } from "@/lib/format";
import { Badge, Breadcrumbs, SkeletonCards } from "@/components/ui";

export const metadata: Metadata = { title: "Learn" };

export default function LearnPage() {
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Learn" }]} />
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Choose your class and subject</h1>
      <p className="mb-6 text-muted">Class XI and Class XII use different textbooks and are listed separately.</p>
      <Suspense fallback={<SkeletonCards count={10} label="Loading subjects" />}>
        <GradeSubjects />
      </Suspense>
    </div>
  );
}

async function GradeSubjects() {
  const res = await getCatalogue();
  if (!res.ok) throw new Error(res.problem.detail);
  return (
    <div className="grid gap-8 md:grid-cols-2">
      {res.data.grades.map((g) => (
        <section key={g.grade.id} aria-labelledby={`grade-${g.grade.number}`}>
          <h2 id={`grade-${g.grade.number}`} className="mb-3 text-lg font-semibold">
            {GRADE_LABEL[g.grade.number] ?? g.grade.name}
          </h2>
          <ul className="space-y-2">
            {g.subjects.map(({ subject, books }) => {
              const book = books[0];
              return (
                <li key={subject.id}>
                  {book ? (
                    <Link
                      href={`/learn/${g.grade.number}/${subject.code}`}
                      className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-3 hover:border-accent"
                    >
                      <span>
                        <span className="block font-medium">{subject.name}</span>
                        <span className="text-sm text-muted">
                          {book.chapter_count} {book.chapter_label.toLowerCase()}s
                        </span>
                      </span>
                      {book.completeness !== "complete" && <Badge tone="warn">Source has gaps</Badge>}
                    </Link>
                  ) : (
                    <div className="rounded-xl border border-dashed border-border px-4 py-3 text-muted">
                      {subject.name} — no textbook available yet
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
