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
import { ButtonLink, buttonClasses } from "@/components/button";
import { GlassCard, GlassCardLink } from "@/components/glass-card";
import { Icon, SubjectIcon } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { SectionHeader } from "@/components/section-header";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { taughtBooks } from "@/lib/subjects";

export const metadata: Metadata = { title: "Learn" };

const TRACK_CODES = ["pre_medical", "pre_engineering", "ics"];
const pick = (v: string | string[] | undefined, allowed: string[]) => (typeof v === "string" && allowed.includes(v) ? v : undefined);
const LINK = "font-medium text-accent underline underline-offset-2";

/**
 * Learn (pilot): choose your class, then your study group, and see that class's books for that group. A signed-in
 * learner's profile sets both; a guest's choice stays in a cookie on this device. Every book can still be browsed.
 * DESIGN-01 (draft C · Soft Glass): an open hero on the mesh, the chooser and books as glass cards.
 */
export default function LearnPage({ searchParams }: PageProps<"/learn">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Learn" }]} />
        <PageHero
          className="!pt-2 !pb-0 sm:!pt-6"
          eyebrow="Class 11 · Class 12"
          title="Learn"
          lead="Choose your class and study group to see your Punjab textbooks. Class 11 and Class 12 stay separate."
        />
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
    <div className="space-y-10">
      {context ? (
        <GlassCard className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <span aria-hidden className="grid size-11 shrink-0 place-items-center rounded-inner bg-accent-soft text-accent">
              <Icon name="layers" size={20} />
            </span>
            <div className="min-w-0">
              <p className="font-display text-lg font-semibold">
                {GRADE_LABEL[context.grade]} · {STREAM_LABEL[context.stream]}
              </p>
              <p className="text-sm text-muted">
                {resolved.source === "profile" ? "From your profile" : user ? "Chosen on this device" : "Chosen on this device · sign in to keep it"}
              </p>
            </div>
          </div>
          <ButtonLink href="/learn?change=1" variant="secondary" aria-label="Change class or study group">
            Change
          </ButtonLink>
        </GlassCard>
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
  const chip =
    "flex min-h-11 cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium transition duration-200 hover:border-accent has-[:checked]:border-accent has-[:checked]:bg-accent-soft has-[:checked]:font-semibold";
  return (
    <form action={chooseLearnContext} className="glass space-y-6 rounded-card p-[22px] sm:p-7" aria-labelledby="choose-heading">
      <div className="space-y-1">
        <h2 id="choose-heading" className="font-display text-2xl font-semibold tracking-tight">
          What are you studying?
        </h2>
        <p className="text-sm text-muted">Class 11 and Class 12 use different textbooks, so choose both.</p>
      </div>
      <fieldset className="space-y-3">
        <legend className="mb-3 flex items-center gap-2 font-semibold">
          <span aria-hidden className="grid size-6 place-items-center rounded-full bg-foreground text-xs text-background">
            1
          </span>
          <span className="sr-only">1. </span>Your class
        </legend>
        <div className="flex flex-wrap gap-2">
          {GRADES.map(([g, label]) => (
            <label key={g} className={chip}>
              <input type="radio" name="grade" value={g} defaultChecked={partial.grade === g} required className="size-4 accent-accent" />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-3">
        <legend className="mb-3 flex items-center gap-2 font-semibold">
          <span aria-hidden className="grid size-6 place-items-center rounded-full bg-foreground text-xs text-background">
            2
          </span>
          <span className="sr-only">2. </span>Your study group
        </legend>
        <div className="flex flex-wrap gap-2">
          {STREAMS.map(([code, label, subjects]) => (
            <label key={code} className={chip} title={subjects}>
              <input type="radio" name="stream" value={code} defaultChecked={partial.stream === code} required className="size-4 accent-accent" />
              {label}
            </label>
          ))}
        </div>
        <p className="text-sm text-muted">
          {partial.stream ? STREAMS.find(([code]) => code === partial.stream)?.[2] : "Pre-Medical, Pre-Engineering or ICS."}
          {tracks?.find((t) => t.code === partial.stream)?.note ? ` ${tracks.find((t) => t.code === partial.stream)?.note}` : ""}
        </p>
      </fieldset>
      <button type="submit" className={buttonClasses({ size: "lg" })}>
        Show my subjects
        <Icon name="arrow-right" size={18} />
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
    <GlassCardLink href={`/learn/chapter/${next.chapter_id}#lesson-${next.lesson_id}`} className="group flex items-center gap-4">
      <span aria-hidden className="grid size-11 shrink-0 place-items-center rounded-full bg-foreground text-background">
        <Icon name="play" size={18} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-xs font-semibold tracking-[0.15em] text-accent uppercase">Continue reading</span>
        <span className="block font-display text-lg font-semibold group-hover:text-accent">{next.title}</span>
        <span className="block text-sm text-muted">
          {GRADE_LABEL[next.grade]} · Chapter {next.chapter_number}: {next.chapter_title}
        </span>
      </span>
      <Icon name="arrow-right" size={20} className="shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" />
    </GlassCardLink>
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

/** A book as a glass card in its subject's colour: the subject tile, its name, what is published, then its badges. */
function BookCard({ b }: { b: Discovery["books"][number] }) {
  return (
    <li data-subject={subjectKey(b.subject)}>
      <GlassCardLink href={`/learn/${b.grade}/${b.subject}`} className="group flex h-full items-start gap-4">
        <SubjectIcon subject={b.subject} size={44} />
        <span className="flex min-w-0 flex-1 flex-col gap-1.5">
          <span className="flex items-start justify-between gap-2">
            <span className="font-display text-lg leading-snug font-semibold group-hover:text-accent">{b.subject_name}</span>
            <Icon name="arrow-right" size={18} className="mt-1 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" />
          </span>
          <span className="block text-sm text-muted">
            {b.chapter_count} {b.chapter_label.toLowerCase()}s · {summary(b)}
          </span>
          {(b.preview_lessons > 0 || b.completeness !== "complete") && (
            <span className="flex flex-wrap gap-1.5 pt-1">
              {b.preview_lessons > 0 && <Badge tone="ok">Free previews</Badge>}
              {b.completeness !== "complete" && <Badge tone="warn">Source has gaps</Badge>}
            </span>
          )}
        </span>
      </GlassCardLink>
    </li>
  );
}

/** Reviewed lessons anyone can read, as a glass list (navigation only; the lessons open on solid pages). */
function PreviewList({ previews }: { previews: Discovery["previews"] }) {
  return (
    <GlassCard as="div" padded={false} className="overflow-hidden">
      <ul className="divide-y divide-border text-sm">
        {previews.map((p) => (
          <li key={p.lesson_id} className="flex items-start gap-3 px-5 py-3.5" data-subject={subjectKey(p.subject_name)}>
            <Icon name="book-open" size={18} className="mt-0.5 shrink-0 text-accent" />
            <span>
              <Link href={`/learn/chapter/${p.chapter_id}#lesson-${p.lesson_id}`} className={LINK}>
                {p.title}
              </Link>
              <span className="text-muted">
                {" "}
                · {GRADE_LABEL[p.grade]} {p.subject_name} · Chapter {p.chapter_number}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </GlassCard>
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
  const books = taughtBooks(d.books).filter((b) => b.grade === context.grade);
  const previews = d.previews.filter((p) => p.grade === context.grade);
  const note = d.tracks.find((t) => t.code === context.stream)?.note;
  return (
    <div className="space-y-10">
      <section aria-labelledby="subjects-h" className="space-y-3">
        <SectionHeader id="subjects-h" title="Your subjects" description={note} className="!mb-2" />
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
          <ul className="grid gap-4 md:grid-cols-3">
            {books.map((b) => (
              <BookCard key={b.book_id} b={b} />
            ))}
          </ul>
        )}
      </section>
      {previews.length > 0 && (
        <section aria-labelledby="previews-h" className="space-y-3">
          <SectionHeader id="previews-h" title="Free preview lessons" className="!mb-2" />
          <PreviewList previews={previews} />
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
 * Every published book, Class 11 and Class 12 kept separate (DISCOVERY-01), while no class and group are chosen.
 * A group or class already named (a track link from the home page, a half-made choice) narrows the list.
 */
async function AllBooks({ partial }: { partial: Partial<LearnContext> }) {
  const res = await getDiscovery({ grade: partial.grade ? String(partial.grade) : undefined, track: partial.stream });
  if (!res.ok) return <Notice tone="warn" title="Couldn't load the books">{res.problem.detail}</Notice>;
  const d = res.data;
  const grades = [11, 12].filter((g) => taughtBooks(d.books).some((b) => b.grade === g));
  const title = partial.stream ? `${STREAM_LABEL[partial.stream]} books` : "Browse every book";
  return (
    <div className="space-y-10">
      <SectionHeader
        id="books-h"
        title={title}
        className="!mb-0"
        description={
          <>
            Each book shows what has been reviewed and published so far.
            {partial.stream ? (
              <>
                {" "}
                <Link href="/learn?change=1" className="underline underline-offset-2">
                  Show every book
                </Link>
              </>
            ) : null}
          </>
        }
      />
      {d.ambiguous_editions.length > 0 && (
        <Notice tone="warn" title="More than one edition is effective today">
          {d.ambiguous_editions.map((a) => `${GRADE_LABEL[a.grade] ?? `Class ${a.grade}`} ${a.subject_name}`).join("; ")}. None of those books is shown,
          because the portal does not choose an edition for you. An edition you already have a link for can still be opened.
        </Notice>
      )}
      <div className="grid gap-8 md:grid-cols-2">
        {grades.map((g) => (
          <section key={g} aria-labelledby={`grade-${g}`} className="space-y-3">
            <h3 id={`grade-${g}`} className="flex items-center gap-2 font-display text-xl font-semibold tracking-tight">
              <span aria-hidden className="h-5 w-1 rounded-full bg-foreground/70" />
              {GRADE_LABEL[g]}
            </h3>
            <ul className="space-y-3">
              {taughtBooks(d.books)
                .filter((b) => b.grade === g)
                .map((b) => (
                  <BookCard key={b.book_id} b={b} />
                ))}
            </ul>
          </section>
        ))}
      </div>
      {d.previews.length > 0 && (
        <section aria-labelledby="previews-h" className="space-y-3">
          <SectionHeader id="previews-h" title="Free preview lessons" description="Reviewed lessons anyone can read, no sign-in needed." className="!mb-2" />
          <PreviewList previews={d.previews} />
        </section>
      )}
      <p className="text-sm text-muted">{d.plans_note}</p>
    </div>
  );
}
