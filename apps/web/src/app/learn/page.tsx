import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Suspense } from "react";
import type { Dashboard, Discovery } from "@portal/contracts";
import { chooseLearnContext } from "@/app/actions/learn";
import { getDiscovery } from "@/lib/api";
import { GRADE_LABEL } from "@/lib/format";
import {
  GRADES,
  LEARN_COOKIE,
  parseLearnCookie,
  resolveContext,
  STREAM_LABEL,
  STREAMS,
  subjectKey,
  type LearnContext,
} from "@/lib/learn-context";
import { api, currentUser } from "@/lib/session";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";

export const metadata: Metadata = { title: "Learn" };

const TRACK_CODES = ["pre_medical", "pre_engineering", "ics"];
const pick = (v: string | string[] | undefined, allowed: string[]) => (typeof v === "string" && allowed.includes(v) ? v : undefined);

/**
 * Learn (pilot): choose your class, then your study group, and see that class's books for that group. A signed-in
 * learner's profile sets both; a guest's choice stays in a cookie on this device. Every book can still be browsed.
 */
export default function LearnPage({ searchParams }: PageProps<"/learn">) {
  return (
    <div className="space-y-6">
      <div>
        <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Learn" }]} />
        <h1 className="mb-2 text-2xl font-semibold tracking-tight">Learn</h1>
      </div>
      <Suspense fallback={<SkeletonCards count={6} label="Loading subjects" />}>
        {searchParams.then((sp) => (
          <LearnFor grade={pick(sp.grade, ["11", "12"])} track={pick(sp.track, TRACK_CODES)} change={sp.change === "1"} />
        ))}
      </Suspense>
    </div>
  );
}

async function LearnFor({ grade, track, change }: { grade?: string; track?: string; change: boolean }) {
  const user = await currentUser();
  const device = parseLearnCookie((await cookies()).get(LEARN_COOKIE)?.value);
  const fromUrl: Partial<LearnContext> = {};
  if (grade) fromUrl.grade = Number(grade) as LearnContext["grade"];
  if (track) fromUrl.stream = track as LearnContext["stream"];
  const resolved = resolveContext(user?.me.profile, { ...device, ...fromUrl });
  const partial = { ...resolved.partial, ...fromUrl };
  const context = change ? null : resolved.context;
  return (
    <div className="space-y-8">
      {context ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-3">
          <div>
            <p className="font-semibold">
              {GRADE_LABEL[context.grade]} · {STREAM_LABEL[context.stream]}
            </p>
            <p className="text-sm text-muted">{resolved.source === "profile" ? "From your profile" : user ? "Chosen on this device" : "Chosen on this device · sign in to keep it"}</p>
          </div>
          <Link href="/learn?change=1" className="text-sm font-medium text-accent underline underline-offset-2" aria-label="Change class or study group">
            Change
          </Link>
        </div>
      ) : (
        <Chooser partial={partial} tracks={null} />
      )}
      {user && <ContinueReading token={user.token} />}
      <Suspense fallback={<SkeletonCards count={3} label="Loading subjects" />}>
        {context ? <Subjects context={context} /> : <AllBooks partial={partial} />}
      </Suspense>
    </div>
  );
}

function Chooser({ partial, tracks }: { partial: Partial<LearnContext>; tracks: Discovery["tracks"] | null }) {
  const chip = "flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 has-[:checked]:border-accent has-[:checked]:bg-accent-soft";
  return (
    <form action={chooseLearnContext} className="space-y-5 rounded-xl border border-border bg-surface p-5" aria-labelledby="choose-heading">
      <div>
        <h2 id="choose-heading" className="text-lg font-semibold">
          What are you studying?
        </h2>
        <p className="text-sm text-muted">Class XI and Class XII use different textbooks, so choose both.</p>
      </div>
      <fieldset className="space-y-2">
        <legend className="font-medium">1. Your class</legend>
        <div className="flex flex-wrap gap-2">
          {GRADES.map(([g, label]) => (
            <label key={g} className={chip}>
              <input type="radio" name="grade" value={g} defaultChecked={partial.grade === g} required />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-2">
        <legend className="font-medium">2. Your study group</legend>
        <div className="flex flex-wrap gap-2">
          {STREAMS.map(([code, label, subjects]) => (
            <label key={code} className={chip} title={subjects}>
              <input type="radio" name="stream" value={code} defaultChecked={partial.stream === code} required />
              {label}
            </label>
          ))}
        </div>
        <p className="text-sm text-muted">
          {partial.stream ? STREAMS.find(([code]) => code === partial.stream)?.[2] : "Pre-Medical, Pre-Engineering or ICS."}
          {tracks?.find((t) => t.code === partial.stream)?.note ? ` ${tracks.find((t) => t.code === partial.stream)?.note}` : ""}
        </p>
      </fieldset>
      <button type="submit" className="rounded-lg bg-accent px-5 py-2.5 font-medium text-white hover:bg-accent-strong dark:text-background">
        Show my subjects
      </button>
    </form>
  );
}

/** Only a real reading position (a published lesson this learner opened) becomes "Continue reading". */
async function ContinueReading({ token }: { token: string }) {
  const res = await api<Dashboard>("/v1/me/dashboard", { token });
  if (!res.ok) return null;
  const next = res.data.continue_learning;
  if (!next) return null;
  return (
    <Link href={`/learn/chapter/${next.chapter_id}#lesson-${next.lesson_id}`} className="block rounded-xl border border-border bg-surface px-4 py-3 hover:border-accent">
      <span className="block text-sm font-medium text-accent">Continue reading</span>
      <span className="block font-semibold">{next.title}</span>
      <span className="block text-sm text-muted">
        {GRADE_LABEL[next.grade]} · Chapter {next.chapter_number}: {next.chapter_title}
      </span>
    </Link>
  );
}

function summary(b: Discovery["books"][number]): string {
  if (b.state === "not_yet_published") return "No reviewed lessons or practice questions published yet.";
  const parts = [];
  if (b.live_lessons) parts.push(`${b.live_lessons} reviewed lesson${b.live_lessons === 1 ? "" : "s"} in ${b.chapters_with_lessons} ${b.chapter_label.toLowerCase()}${b.chapters_with_lessons === 1 ? "" : "s"}`);
  else parts.push("No reviewed lessons yet");
  if (b.preview_lessons) parts.push(`${b.preview_lessons} free preview${b.preview_lessons === 1 ? "" : "s"}`);
  if (b.practice_questions) parts.push(`${b.practice_questions} practice question${b.practice_questions === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

function BookCard({ b }: { b: Discovery["books"][number] }) {
  return (
    <li>
      <Link
        href={`/learn/${b.grade}/${b.subject}`}
        data-subject={subjectKey(b.subject)}
        className="flex items-start justify-between gap-3 rounded-xl border border-border border-l-4 border-l-accent bg-surface px-4 py-3 hover:border-accent"
      >
        <span>
          <span className="block font-semibold">{b.subject_name}</span>
          <span className="block text-sm text-muted">
            {b.chapter_count} {b.chapter_label.toLowerCase()}s · {summary(b)}
          </span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1">
          {b.preview_lessons > 0 && <Badge tone="ok">Free previews</Badge>}
          {b.completeness !== "complete" && <Badge tone="warn">Source has gaps</Badge>}
        </span>
      </Link>
    </li>
  );
}

/** The chosen class's books for the chosen group (the API's track filter decides which books those are). */
async function Subjects({ context }: { context: LearnContext }) {
  const res = await getDiscovery({ grade: String(context.grade), track: context.stream });
  if (!res.ok) {
    return (
      <Notice tone="warn" title="Couldn't load these subjects">
        {res.problem.detail} <Link href="/learn?change=1" className="underline">Choose again</Link>
      </Notice>
    );
  }
  const d = res.data;
  const books = d.books.filter((b) => b.grade === context.grade);
  const previews = d.previews.filter((p) => p.grade === context.grade);
  const note = d.tracks.find((t) => t.code === context.stream)?.note;
  return (
    <div className="space-y-8">
      <section aria-labelledby="subjects-h" className="space-y-3">
        <h2 id="subjects-h" className="text-lg font-semibold">
          Your subjects
        </h2>
        {note && <p className="text-sm text-muted">{note}</p>}
        {d.ambiguous_editions.length > 0 && (
          <Notice tone="warn" title="More than one edition is effective today">
            {d.ambiguous_editions.map((a) => `${GRADE_LABEL[a.grade] ?? `Class ${a.grade}`} ${a.subject_name}`).join("; ")}. Those books are not shown,
            because the portal does not choose an edition for you.
          </Notice>
        )}
        {books.length === 0 && d.ambiguous_editions.length === 0 ? (
          <Notice title={`No ${GRADE_LABEL[context.grade]} ${STREAM_LABEL[context.stream]} books yet`}>
            <Link href="/learn?change=1" className="underline">Choose another class or group</Link>, or browse every book below.
          </Notice>
        ) : (
          <ul className="grid gap-3 md:grid-cols-3">
            {books.map((b) => (
              <BookCard key={b.book_id} b={b} />
            ))}
          </ul>
        )}
      </section>
      {previews.length > 0 && (
        <section aria-labelledby="previews-h" className="space-y-2">
          <h2 id="previews-h" className="text-lg font-semibold">
            Free preview lessons
          </h2>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {previews.map((p) => (
              <li key={p.lesson_id} className="px-4 py-3">
                <Link href={`/learn/chapter/${p.chapter_id}#lesson-${p.lesson_id}`} className="font-medium text-accent underline underline-offset-2">
                  {p.title}
                </Link>
                <span className="text-muted">
                  {" "}
                  · {GRADE_LABEL[p.grade]} {p.subject_name} · Chapter {p.chapter_number}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-sm text-muted">
        {d.plans_note}{" "}
        <Link href="/learn?change=1" className="underline underline-offset-2">
          Browse every book
        </Link>
      </p>
    </div>
  );
}

/**
 * Every published book, Class XI and Class XII kept separate (DISCOVERY-01), while no class and group are chosen.
 * A group or class already named (a track link from the home page, a half-made choice) narrows the list.
 */
async function AllBooks({ partial }: { partial: Partial<LearnContext> }) {
  const res = await getDiscovery({ grade: partial.grade ? String(partial.grade) : undefined, track: partial.stream });
  if (!res.ok) return <Notice tone="warn" title="Couldn't load the books">{res.problem.detail}</Notice>;
  const d = res.data;
  const grades = [11, 12].filter((g) => d.books.some((b) => b.grade === g));
  const title = partial.stream ? `${STREAM_LABEL[partial.stream]} books` : "Browse every book";
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-muted">
          Each book shows what has been reviewed and published so far.
          {partial.stream ? (
            <>
              {" "}
              <Link href="/learn?change=1" className="underline underline-offset-2">
                Show every book
              </Link>
            </>
          ) : null}
        </p>
      </div>
      {d.ambiguous_editions.length > 0 && (
        <Notice tone="warn" title="More than one edition is effective today">
          {d.ambiguous_editions.map((a) => `${GRADE_LABEL[a.grade] ?? `Class ${a.grade}`} ${a.subject_name}`).join("; ")}. None of those books is shown,
          because the portal does not choose an edition for you. An edition you already have a link for can still be opened.
        </Notice>
      )}
      <div className="grid gap-8 md:grid-cols-2">
        {grades.map((g) => (
          <section key={g} aria-labelledby={`grade-${g}`}>
            <h3 id={`grade-${g}`} className="mb-3 text-lg font-semibold">
              {GRADE_LABEL[g]}
            </h3>
            <ul className="space-y-2">
              {d.books
                .filter((b) => b.grade === g)
                .map((b) => (
                  <BookCard key={b.book_id} b={b} />
                ))}
            </ul>
          </section>
        ))}
      </div>
      {d.previews.length > 0 && (
        <section aria-labelledby="previews-h" className="space-y-2">
          <h2 id="previews-h" className="text-lg font-semibold">
            Free preview lessons
          </h2>
          <p className="text-sm text-muted">Reviewed lessons anyone can read, no sign-in needed.</p>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {d.previews.map((p) => (
              <li key={p.lesson_id} className="px-4 py-3">
                <Link href={`/learn/chapter/${p.chapter_id}#lesson-${p.lesson_id}`} className="font-medium text-accent underline underline-offset-2">
                  {p.title}
                </Link>
                <span className="text-muted">
                  {" "}
                  · {GRADE_LABEL[p.grade]} {p.subject_name} · Chapter {p.chapter_number}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-sm text-muted">{d.plans_note}</p>
    </div>
  );
}
