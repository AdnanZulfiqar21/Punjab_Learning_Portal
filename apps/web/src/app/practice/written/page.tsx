import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { GlassCard } from "@/components/glass-card";
import { PageHero } from "@/components/page-hero";
import { ClassSubjectFilter } from "@/components/practice-ui";
import { Breadcrumbs, Notice, SkeletonCards, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { SUBJECTS } from "@/lib/practice";
import { taughtSubjects } from "@/lib/practice-filters";
import { currentUser } from "@/lib/session";
import { getWrittenAvailability } from "@/lib/written";
import { getAccess } from "@/lib/access";
import { PlanStatus } from "@/components/plan-status";
import { WrittenBuilder } from "./written-builder";

export const metadata: Metadata = { title: "Written practice", robots: { index: false } };

export default function WrittenPracticePage({ searchParams }: PageProps<"/practice/written">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Written practice" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · Teacher-marked"
          title="Written practice"
          lead="Answer short and long questions on paper, photograph or scan your pages, and submit them for a teacher to mark. Only questions with an approved marking rubric are used."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense
        fallback={
          <div className="space-y-4">
            <SkeletonCards count={2} label="Loading written practice" />
            <SkeletonLines lines={6} label="Loading chapters" />
          </div>
        }
      >
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
      <ClassSubjectFilter path="/practice/written" grade={grade} subject={subject} subjects={taughtSubjects(SUBJECTS)} />
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
          {/* WORKLOAD-GUARD-01: new written tests wait out a short pause that protects exams in progress. */}
          {av.paused ? (
            <Notice tone="warn" title="Written tests are paused for a few minutes">
              {av.guard_notice}
            </Notice>
          ) : (
            av.guard_notice && <p className="text-sm text-muted">{av.guard_notice}</p>
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
          <GlassCard className="sm:p-7">
            <WrittenBuilder grade={grade} subject={subject} chapters={av.chapters} uploadAllowanceS={av.upload_allowance_s} caps={av.caps} />
          </GlassCard>
        </>
      )}
    </div>
  );
}
