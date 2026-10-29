import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { MockReadiness, MockSession, PublishedExamProfile } from "@portal/contracts";
import { GlassCard } from "@/components/glass-card";
import { PageHero } from "@/components/page-hero";
import { PracticeIcon } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { StatChip } from "@/components/stat-chip";
import { Badge, Breadcrumbs, Notice, SkeletonCards, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { JoinSession } from "./join-session";
import { StartMock } from "./start-mock";

export const metadata: Metadata = { title: "Mock tests", robots: { index: false } };

export default function MocksPage() {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Mock tests" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · Official patterns"
          title="Mock tests"
          lead="Full-length tests that follow an official test pattern, as verified by two reviewers. Taking a mock doesn't affect admission eligibility."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonLines lines={3} label="Loading scheduled mocks" />}>
        <Sessions />
      </Suspense>
      <Suspense fallback={<SkeletonCards count={2} label="Loading test patterns" />}>
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
        <Link href="/practice" className="font-medium text-accent underline underline-offset-2">
          build a practice test
        </Link>
        .
      </Notice>
    );
  }
  const ready = await Promise.all(res.data.map((p) => api<MockReadiness>(`/v1/mocks/${encodeURIComponent(p.code)}/readiness`, { token: user.token })));
  return (
    <ul className="grid gap-4 lg:grid-cols-2" aria-label="Test patterns">
      {res.data.map((p, i) => {
        const r = ready[i].ok ? ready[i].data : null;
        return (
          <GlassCard as="li" key={p.code} className="flex flex-col gap-3">
            <div className="flex items-start gap-3">
              <span aria-hidden="true" className="inline-grid size-11 shrink-0 place-items-center rounded-inner bg-accent-soft text-accent ring-1 ring-accent/20">
                <PracticeIcon name="timer" size={22} />
              </span>
              <h2 className="min-w-0 flex-1 pt-1.5 font-display text-lg leading-snug font-semibold">{p.name}</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{p.year}</Badge>
              {r?.ready ? (
                <Badge tone="ok">Ready</Badge>
              ) : (
                <Badge tone="warn">{r && r.problems.length > 0 ? "Not available yet" : "Not enough questions yet"}</Badge>
              )}
            </div>
            <p className="flex flex-wrap gap-2">
              <StatChip icon="list-checks">{p.total_questions} questions</StatChip>
              <StatChip>
                <PracticeIcon name="timer" size={16} className="text-accent" />
                {p.duration_minutes} minutes
              </StatChip>
            </p>
            <p className="text-sm text-muted capitalize">{p.sections.map((s) => `${String(s.subject).replace("_", " ")} ${String(s.questions)}`).join(", ")}</p>
            {p.eligibility_note && <p className="text-sm">{p.eligibility_note}</p>}
            <a href={p.source_url} rel="noopener noreferrer" target="_blank" className="inline-flex min-h-11 items-center self-start text-sm font-medium text-accent underline underline-offset-2">
              Official source
            </a>
            {r && !r.ready && (
              <ul className="list-disc space-y-1 rounded-inner bg-surface-muted/70 py-3 pr-4 pl-8 text-sm text-muted">
                {/* P05.S4.T3: the pattern doesn't match the current books (for example two editions of one book). */}
                {r.problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
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
            {r?.ready && r.entitled && (
              <div className="mt-auto pt-1">
                <StartMock code={p.code} />
              </div>
            )}
            {r?.ready && !r.entitled && (
              <p className="mt-auto text-sm">
                Mock tests are included with a plan or the free 30-day trial.{" "}
                <Link href="/account" className="text-accent underline underline-offset-2">
                  Start your free trial or see your plan
                </Link>
              </p>
            )}
          </GlassCard>
        );
      })}
    </ul>
  );
}

const when = (iso: string, tz: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: tz });

async function Sessions() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice/mocks");
  const res = await api<MockSession[]>("/v1/mock-sessions", { token: user.token });
  if (!res.ok || res.data.length === 0) return null;
  return (
    <section aria-labelledby="sessions-h">
      <SectionHeader id="sessions-h" title="Scheduled mocks" />
      <ul className="space-y-4" aria-label="Scheduled mocks">
        {res.data.map((s) => (
          <GlassCard as="li" key={s.id} className="space-y-2 text-sm">
            <p className="flex flex-wrap items-center gap-2">
              <span className="font-display text-base font-semibold">{s.title}</span>
              <Badge tone={s.state === "open" ? "ok" : s.state === "upcoming" ? "info" : "warn"}>
                {s.state === "open" ? "Open now" : s.state === "upcoming" ? "Upcoming" : "Entry closed"}
              </Badge>
            </p>
            <p className="text-muted">
              {s.profile_name} · {s.total_questions} questions · {s.duration_minutes} minutes · starts {when(s.starts_at, s.timezone)} · late entry until{" "}
              {when(s.entry_closes_at, s.timezone)} · results {when(s.results_at, s.timezone)} ({s.timezone})
            </p>
            <p className="text-muted">
              {s.late_entry === "fixed_end"
                ? "Everyone finishes at the same time, so joining late leaves you less time."
                : "You get the full time from when you join, until the window closes."}
            </p>
            {s.state === "open" && (
              <div className="pt-1">
                <JoinSession id={s.id} />
              </div>
            )}
          </GlassCard>
        ))}
      </ul>
    </section>
  );
}
