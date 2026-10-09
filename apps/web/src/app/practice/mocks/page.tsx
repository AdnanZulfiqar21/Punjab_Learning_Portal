import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { MockReadiness, PublishedExamProfile } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { StartMock } from "./start-mock";

export const metadata: Metadata = { title: "Mock tests", robots: { index: false } };

export default function MocksPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Mock tests" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Mock tests</h1>
        <p className="text-muted">
          Full-length tests that follow an official test pattern, as verified by two reviewers. Taking a mock doesn&apos;t affect admission eligibility.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={4} label="Loading test patterns" />}>
        <Patterns />
      </Suspense>
    </div>
  );
}

async function Patterns() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice/mocks");
  const res = await api<PublishedExamProfile[]>("/v1/exam-profiles", { token: user.token });
  if (!res.ok) return <Notice tone="warn" title="Couldn't load test patterns">{res.problem?.detail ?? "Please try again."}</Notice>;
  if (res.data.length === 0) {
    return (
      <Notice title="No mock tests yet">
        Mock tests appear once an official test pattern has been checked by two reviewers. Meanwhile,{" "}
        <Link href="/practice" className="underline">
          build a practice test
        </Link>
        .
      </Notice>
    );
  }
  const ready = await Promise.all(res.data.map((p) => api<MockReadiness>(`/v1/mocks/${encodeURIComponent(p.code)}/readiness`, { token: user.token })));
  return (
    <ul className="space-y-4" aria-label="Test patterns">
      {res.data.map((p, i) => {
        const r = ready[i].ok ? ready[i].data : null;
        return (
          <li key={p.code} className="space-y-2 rounded-xl border border-border bg-surface p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold">{p.name}</h2>
              <Badge>{p.year}</Badge>
              {r?.ready ? <Badge tone="ok">Ready</Badge> : <Badge tone="warn">Not enough questions yet</Badge>}
            </div>
            <p className="text-sm text-muted">
              {p.total_questions} questions · {p.duration_minutes} minutes ·{" "}
              {p.sections.map((s) => `${String(s.subject).replace("_", " ")} ${String(s.questions)}`).join(", ")}
            </p>
            {p.eligibility_note && <p className="text-sm">{p.eligibility_note}</p>}
            <a href={p.source_url} rel="noopener noreferrer" target="_blank" className="text-sm text-accent underline underline-offset-2">
              Official source
            </a>
            {r && !r.ready && (
              <ul className="text-sm text-muted">
                {r.sections
                  .filter((s) => !s.enough)
                  .map((s) => (
                    <li key={String(s.subject)}>
                      {String(s.subject).replace("_", " ")}: {String(s.available)} of {String(s.questions)} approved questions available
                    </li>
                  ))}
                {r.scheduled && <li>This pattern uses a scheduled window, which isn&apos;t available yet.</li>}
              </ul>
            )}
            {r?.ready && <StartMock code={p.code} />}
          </li>
        );
      })}
    </ul>
  );
}
