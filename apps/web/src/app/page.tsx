import Link from "next/link";
import { Suspense } from "react";
import type { Dashboard } from "@portal/contracts";
import { DashboardView } from "@/components/dashboard";
import { Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

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
  return <DashboardView d={res.data} email={user.me.email ?? ""} />;
}

function Welcome() {
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
      <section aria-labelledby="subjects-heading" className="space-y-3">
        <h2 id="subjects-heading" className="text-lg font-semibold">
          Subjects
        </h2>
        <ul className="flex flex-wrap gap-2">
          {SUBJECTS.map((s) => (
            <li key={s} className="rounded-full border border-border bg-surface px-3 py-1 text-sm">
              {s}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
