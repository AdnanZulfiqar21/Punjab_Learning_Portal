import Link from "next/link";
import { Suspense } from "react";
import type { Dashboard, Discovery } from "@portal/contracts";
import { DashboardView } from "@/components/dashboard";
import { Notice, SkeletonLines } from "@/components/ui";
import { getDiscovery } from "@/lib/api";
import { api, currentUser, features } from "@/lib/session";

const SUBJECTS = ["Biology", "Chemistry", "Physics", "Computer Science", "Mathematics"];

export default function Home() {
  return (
    <Suspense fallback={<SkeletonLines lines={6} label="Loading" />}>
      <HomeFor />
    </Suspense>
  );
}

/** Signed-in learners get their dashboard (P11.S1.T2); everyone else sees the introduction. */
async function HomeFor() {
  const user = await currentUser();
  if (!user) return <Welcome />;
  const res = await api<Dashboard>("/v1/me/dashboard", { token: user.token });
  if (!res.ok) {
    return <Notice tone="warn" title="Couldn't load your dashboard">{res.problem?.detail ?? "Please try again."}</Notice>;
  }
  const flags = await features(user.token);
  return <DashboardView d={res.data} email={user.me.email ?? ""} studyTools={flags.study_tools === true} />;
}

/** P11.S1.T1 (PUBLIC-SITE-01): courses, tracks and honest coverage from what is actually published (DISCOVERY-01). */
async function Welcome() {
  let d: Discovery | null = null;
  try {
    const res = await getDiscovery({});
    d = res.ok ? res.data : null;
  } catch {
    d = null; // the introduction still works when the learning service is unreachable
  }
  const lessons = d?.books.reduce((n, b) => n + b.live_lessons, 0) ?? 0;
  const previews = d?.books.reduce((n, b) => n + b.preview_lessons, 0) ?? 0;
  const outlineOnly = d?.books.filter((b) => b.state === "not_yet_published").length ?? 0;
  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Study Class XI and XII the way your textbook does.</h1>
        <p className="max-w-2xl text-lg text-muted">
          Every chapter and topic is organised from the official Punjab textbooks, with page references back to the book.
          Class XI and Class XII stay separate, so you always know exactly which book you are studying.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/learn"
            className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong dark:text-background"
          >
            Browse chapters
          </Link>
          <Link href="/search" className="rounded-lg border border-border bg-surface px-5 py-3 font-medium hover:bg-surface-muted">
            Search a topic
          </Link>
        </div>
      </section>

      <section aria-labelledby="tracks-heading" className="space-y-3">
        <h2 id="tracks-heading" className="text-lg font-semibold">
          Tracks and subjects
        </h2>
        {d ? (
          <ul className="grid gap-3 sm:grid-cols-3">
            {d.tracks.map((t) => (
              <li key={t.code} className="space-y-1 rounded-xl border border-border bg-surface p-4">
                <Link href={`/learn?track=${t.code}`} className="font-medium text-accent underline-offset-2 hover:underline">
                  {t.name}
                </Link>
                <p className="text-sm text-muted capitalize">{t.subjects.map((s) => s.replace("_", " ")).join(", ")}</p>
                {t.note && <p className="text-xs text-muted">{t.note}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {SUBJECTS.map((s) => (
              <li key={s} className="rounded-full border border-border bg-surface px-3 py-1 text-sm">
                {s}
              </li>
            ))}
          </ul>
        )}
      </section>

      {d && (
        <section aria-labelledby="coverage-heading" className="space-y-2">
          <h2 id="coverage-heading" className="text-lg font-semibold">
            What is published so far
          </h2>
          <p className="max-w-2xl text-sm">
            Lessons are published only after an independent subject reviewer approves them, so coverage grows book by book.
            Right now there {lessons === 1 ? "is" : "are"} <strong>{lessons}</strong> reviewed lesson{lessons === 1 ? "" : "s"}
            {previews > 0 && (
              <>
                {" "}
                (<Link href="/learn?availability=previews" className="text-accent underline underline-offset-2">{previews} free to preview</Link>)
              </>
            )}
            {outlineOnly > 0 && `, and ${outlineOnly} of ${d.books.length} books so far have the chapter outline and textbook page references only`}.
          </p>
          <Link href="/learn" className="text-sm text-accent underline underline-offset-2">
            See coverage book by book
          </Link>
        </section>
      )}

      <section aria-labelledby="plans-heading" className="space-y-2">
        <h2 id="plans-heading" className="text-lg font-semibold">
          Free previews and the free trial
        </h2>
        <p className="max-w-2xl text-sm text-muted">
          Free preview lessons are open to everyone. Create an account to start a free 30-day trial of everything published.
          {d ? ` ${d.plans_note.split(". ")[0]}.` : ""}
        </p>
        <div className="flex flex-wrap gap-3 text-sm">
          <Link href="/signin" className="text-accent underline underline-offset-2">
            Create an account
          </Link>
          <Link href="/help" className="text-accent underline underline-offset-2">
            Help and questions
          </Link>
        </div>
      </section>
    </div>
  );
}
