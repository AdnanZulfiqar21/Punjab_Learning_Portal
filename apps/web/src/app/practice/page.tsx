import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { getAvailability, SUBJECTS } from "@/lib/practice";
import { currentUser } from "@/lib/session";
import { getAccess } from "@/lib/access";
import { PlanStatus } from "@/components/plan-status";
import { PracticeBuilder } from "./practice-builder";

export const metadata: Metadata = { title: "Practice", robots: { index: false } };

export default function PracticePage({ searchParams }: PageProps<"/practice">) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Practice</h1>
        <p className="text-muted">
          Build a test from chapters of your textbook. Only questions approved by an independent subject reviewer are used.
        </p>
        <p className="mt-2 text-sm">
          <Link href="/practice/written" className="text-accent underline-offset-2 hover:underline">
            Written practice (answer on paper, teacher-marked) →
          </Link>
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading practice options" />}>
        {searchParams.then((sp) => (
          <Builder grade={typeof sp.grade === "string" ? sp.grade : undefined} subject={typeof sp.subject === "string" ? sp.subject : undefined} />
        ))}
      </Suspense>
    </div>
  );
}

async function Builder({ grade: rawGrade, subject: rawSubject }: { grade?: string; subject?: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice");
  const profile = user.me.profile;
  const grade = rawGrade === "11" || rawGrade === "12" ? Number(rawGrade) : (profile?.grade ?? 11);
  const subject = SUBJECTS.some(([c]) => c === rawSubject) ? rawSubject! : (profile?.subjects?.[0] ?? "biology");
  const [availability, access] = await Promise.all([getAvailability(user.token, grade, subject), getAccess(user.token)]);
  const total = availability?.chapters.reduce((n, c) => n + c.questions, 0) ?? 0;
  return (
    <div className="space-y-6">
      <nav aria-label="Choose class and subject" className="flex flex-wrap gap-2">
        {[11, 12].map((g) =>
          SUBJECTS.map(([code, name]) => {
            const active = g === grade && code === subject;
            return (
              <Link
                key={`${g}-${code}`}
                href={`/practice?grade=${g}&subject=${code}`}
                aria-current={active ? "page" : undefined}
                className={`rounded-full border px-3 py-1.5 text-sm ${active ? "border-accent bg-accent-soft font-medium text-accent" : "border-border bg-surface hover:border-accent"}`}
              >
                {GRADE_LABEL[g]} {name}
              </Link>
            );
          }),
        )}
      </nav>
      {access && <PlanStatus access={access} purpose="Practice tests" />}
      {access && !access.has_access ? null : !availability || total === 0 ? (
        <Notice title="No approved practice questions yet">
          Questions for {GRADE_LABEL[grade]} {SUBJECTS.find(([c]) => c === subject)?.[1]} appear here once a subject reviewer approves
          them and they are published. Nothing unreviewed is ever used in a test.
        </Notice>
      ) : (
        <PracticeBuilder grade={grade} subject={subject} chapters={availability.chapters} />
      )}
    </div>
  );
}
