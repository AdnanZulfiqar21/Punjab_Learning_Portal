import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { SUBJECTS } from "@/lib/practice";
import { currentUser } from "@/lib/session";
import { getWrittenAvailability } from "@/lib/written";
import { getAccess } from "@/lib/access";
import { PlanStatus } from "@/components/plan-status";
import { WrittenBuilder } from "./written-builder";

export const metadata: Metadata = { title: "Written practice", robots: { index: false } };

export default function WrittenPracticePage({ searchParams }: PageProps<"/practice/written">) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Written practice</h1>
        <p className="text-muted">
          Answer short and long questions on paper, photograph or scan your pages, and submit them for a teacher to mark. Only questions
          with an approved marking rubric are used.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading written practice" />}>
        {searchParams.then((sp) => (
          <Builder grade={typeof sp.grade === "string" ? sp.grade : undefined} subject={typeof sp.subject === "string" ? sp.subject : undefined} />
        ))}
      </Suspense>
    </div>
  );
}

async function Builder({ grade: rawGrade, subject: rawSubject }: { grade?: string; subject?: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice/written");
  const profile = user.me.profile;
  const grade = rawGrade === "11" || rawGrade === "12" ? Number(rawGrade) : (profile?.grade ?? 11);
  const subject = SUBJECTS.some(([c]) => c === rawSubject) ? rawSubject! : (profile?.subjects?.[0] ?? "biology");
  const [av, access] = await Promise.all([getWrittenAvailability(user.token, grade, subject), getAccess(user.token)]);
  const total = av?.chapters.reduce((n, c) => n + c.questions, 0) ?? 0;
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
                href={`/practice/written?grade=${g}&subject=${code}`}
                aria-current={active ? "page" : undefined}
                className={`rounded-full border px-3 py-1.5 text-sm ${active ? "border-accent bg-accent-soft font-medium text-accent" : "border-border bg-surface hover:border-accent"}`}
              >
                {GRADE_LABEL[g]} {label}
              </Link>
            );
          }),
        )}
      </nav>
      {access && <PlanStatus access={access} purpose="Written practice" />}
      {access && !access.has_access ? null : av?.pilot_only && !av.in_pilot ? (
        // PILOT-R0-01: during the R0 pilot only invited pilot learners can start written tests.
        <Notice title="Written practice is in a teacher-reviewed pilot">
          For now, written practice is open only to learners invited to the pilot, and a teacher checks every mark. Your plan&apos;s
          other features are unaffected.
        </Notice>
      ) : !av || !av.review_staffed ? (
        <Notice title="Written practice isn't offered for this subject yet">
          Written answers are marked by teachers, and no teacher reviewer is available for {GRADE_LABEL[grade]} {name} yet.
        </Notice>
      ) : total === 0 ? (
        <Notice title="No written questions yet">
          Written questions for {GRADE_LABEL[grade]} {name} appear here once their question and marking rubric are both approved.
        </Notice>
      ) : (
        <>
          {av.pilot_only && (
            <p className="text-sm text-muted">
              You&apos;re in the written-practice pilot: a teacher checks every mark, and pilot tests use only your pilot marking units.
            </p>
          )}
          {/* STAFFING-01: an honest wait, and a plain notice when marking is full (submitted work is still marked). */}
          {!av.review_accepting ? (
            <Notice tone="warn" title="Marking is full right now">
              Teacher marking for {GRADE_LABEL[grade]} {name} is at capacity, so a new written test can&apos;t start now. Scripts already submitted are kept
              and will be marked.
            </Notice>
          ) : (
            av.turnaround_days != null && (
              <p className="text-sm text-muted">
                Teacher marking currently takes about {av.turnaround_days} day{av.turnaround_days === 1 ? "" : "s"} from when you submit.
              </p>
            )
          )}
          <WrittenBuilder grade={grade} subject={subject} chapters={av.chapters} uploadAllowanceS={av.upload_allowance_s} caps={av.caps} />
        </>
      )}
    </div>
  );
}
