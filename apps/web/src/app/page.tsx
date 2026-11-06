import Link from "next/link";
import { cookies } from "next/headers";
import { Suspense } from "react";
import type { Dashboard, Discovery } from "@portal/contracts";
import { ButtonLink } from "@/components/button";
import { DashboardView } from "@/components/dashboard";
import { GlassCard } from "@/components/glass-card";
import { Icon, type IconName } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { SectionHeader } from "@/components/section-header";
import { SubjectTiles } from "@/components/subject-tiles";
import { Notice, SkeletonCards, SkeletonLines } from "@/components/ui";
import { Marquee } from "@/components/premium/marquee";
import { NumberTicker } from "@/components/premium/number-ticker";
import { SpotlightCard } from "@/components/premium/spotlight-card";
import { TextEffect } from "@/components/premium/text-effect";
import { getBookFor, getDiscovery } from "@/lib/api";
import { subjectKey } from "@/lib/learn-context";
import { taughtBooks } from "@/lib/subjects";
import { LEARN_COOKIE, parseLearnCookie } from "@/lib/learn-context";
import { api, currentUser, features } from "@/lib/session";

const SUBJECTS = ["Biology", "Chemistry", "Physics", "Computer Science", "Mathematics"];

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="space-y-8 pt-10">
          <SkeletonLines lines={3} label="Loading" />
          <SkeletonCards count={4} label="Loading subjects" />
        </div>
      }
    >
      <HomeFor />
    </Suspense>
  );
}

/** The published books, or null when the learning service is unreachable (the home page still works). */
async function discovery(): Promise<Discovery | null> {
  try {
    const res = await getDiscovery({});
    return res.ok ? res.data : null;
  } catch {
    return null;
  }
}

/** Signed-in learners get their dashboard (P11.S1.T2); everyone else sees the introduction. */
async function HomeFor() {
  const user = await currentUser();
  if (!user) return <Welcome d={await discovery()} grade={parseLearnCookie((await cookies()).get(LEARN_COOKIE)?.value).grade} />;
  const [res, d] = await Promise.all([api<Dashboard>("/v1/me/dashboard", { token: user.token }), discovery()]);
  if (!res.ok) {
    return <Notice tone="warn" title="Couldn't load your dashboard">{res.problem?.detail ?? "Please try again."}</Notice>;
  }
  const flags = await features(user.token);
  return <DashboardView d={res.data} email={user.me.email ?? ""} studyTools={flags.study_tools === true} books={d?.books ?? null} />;
}

// DESIGN-01 (draft C): what the portal offers, as it works today. No figures here (owner rule 6).
const FEATURES: { icon: IconName; label: string; title: string; text: string }[] = [
  { icon: "languages", label: "English | Roman Urdu | Lecture", title: "Three ways to read", text: "Book as printed, easy explanation, short lecture." },
  { icon: "play", label: "Run karein", title: "Run the programs", text: "Change values and watch the output change." },
  { icon: "list-checks", label: "Practice", title: "Solved exercises", text: "MCQs, short and long answers, model paper." },
];

/** P11.S1.T1 (PUBLIC-SITE-01): courses, tracks and honest coverage from what is actually published (DISCOVERY-01). */
function Welcome({ d, grade }: { d: Discovery | null; grade?: number }) {
  const lessons = d?.books.reduce((n, b) => n + b.live_lessons, 0) ?? 0;
  const previews = d?.books.reduce((n, b) => n + b.preview_lessons, 0) ?? 0;
  const outlineOnly = d?.books.filter((b) => b.state === "not_yet_published").length ?? 0;
  const link = "font-medium text-accent underline underline-offset-2";
  return (
    <div className="space-y-12">
      <PageHero
        eyebrow="Class 11 · Class 12"
        title={
          // PREMIUM-LOOK-01: the words rise in one by one (CSS only; still for reduced motion), the last line in the
          // subject accent as a gradient.
          <>
            <TextEffect text="Learn your Punjab textbook" />
            <br className="hidden sm:inline" />{" "}
            <TextEffect
              text="the easy way."
              delay={0.35}
              wordClassName="bg-gradient-to-r from-accent to-accent-strong bg-clip-text pb-1 text-transparent"
            />
          </>
        }
        lead="Every chapter is organised from the official Punjab textbooks, in English and easy Roman Urdu, with page references back to the book. Class 11 and Class 12 stay separate."
        actions={
          <>
            <ButtonLink href="/learn" size="lg">
              Start learning
              <Icon name="arrow-right" size={18} />
            </ButtonLink>
            <ButtonLink href="/practice" variant="secondary" size="lg">
              Practice
            </ButtonLink>
            <ButtonLink href="/search" variant="ghost" size="lg">
              <Icon name="search" size={18} />
              Search a topic
            </ButtonLink>
          </>
        }
      />

      {(d?.ambiguous_editions.length ?? 0) > 0 && (
        <Notice tone="warn" title="More than one edition is effective today">
          {d?.ambiguous_editions
            .map((a) => `${a.grade === 11 ? "Class 11" : a.grade === 12 ? "Class 12" : `Class ${a.grade}`} ${a.subject_name}`)
            .join("; ")}
          . None of those books is shown, because the portal does not choose an edition for you.
        </Notice>
      )}

      {d && (
        <Suspense fallback={null}>
          <Stats d={d} />
        </Suspense>
      )}

      <SubjectTiles books={d?.books ?? null} grade={grade} />

      <section aria-labelledby="features-heading">
        <h2 id="features-heading" className="sr-only">
          How you study here
        </h2>
        <ul className="grid gap-4 md:grid-cols-3">
          {FEATURES.map((f) => (
            <li key={f.title}>
              <SpotlightCard className="h-full space-y-1.5 p-[22px]">
                <p className="flex items-center gap-1.5 text-sm text-muted">
                  <Icon name={f.icon} size={16} className="text-accent" />
                  {f.label}
                </p>
                <h3 className="font-display text-lg font-semibold">{f.title}</h3>
                <p className="text-[15px] text-muted">{f.text}</p>
              </SpotlightCard>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="tracks-heading">
        <SectionHeader id="tracks-heading" title="Tracks and subjects" />
        {d ? (
          <ul className="grid gap-4 sm:grid-cols-3">
            {d.tracks.map((t) => (
              <GlassCard as="li" key={t.code} interactive className="space-y-1">
                <Link href={`/learn?track=${t.code}`} className="font-display text-lg font-semibold text-accent underline-offset-2 hover:underline">
                  {t.name}
                </Link>
                <p className="text-sm text-muted capitalize">{t.subjects.map((s) => s.replace("_", " ")).join(", ")}</p>
                {t.note && <p className="text-xs text-muted">{t.note}</p>}
              </GlassCard>
            ))}
          </ul>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {SUBJECTS.map((s) => (
              <li key={s} className="glass rounded-full px-3 py-1 text-sm shadow-none">
                {s}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        {d && (
          <GlassCard as="section" aria-labelledby="coverage-heading" className="space-y-2">
            <h2 id="coverage-heading" className="font-display text-lg font-semibold">
              What is published so far
            </h2>
            <p className="text-sm">
              Lessons are published only after an independent subject reviewer approves them, so coverage grows book by book.
              Right now there {lessons === 1 ? "is" : "are"} <strong>{lessons}</strong> reviewed lesson{lessons === 1 ? "" : "s"}
              {previews > 0 && (
                <>
                  {" "}
                  (<Link href="/learn?availability=previews" className={link}>{previews} free to preview</Link>)
                </>
              )}
              {outlineOnly > 0 && `, and ${outlineOnly} of ${d.books.length} books so far have the chapter outline and textbook page references only`}.
            </p>
            <Link href="/learn" className={`text-sm ${link}`}>
              See coverage book by book
            </Link>
          </GlassCard>
        )}

        <GlassCard as="section" aria-labelledby="plans-heading" className="space-y-2">
          <h2 id="plans-heading" className="font-display text-lg font-semibold">
            Free previews and the free trial
          </h2>
          <p className="text-sm text-muted">
            Free preview lessons are open to everyone. Create an account to start a free 30-day trial of everything published.
            {d ? ` ${d.plans_note.split(". ")[0]}.` : ""}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <Link href="/signin" className={link}>
              Create an account
            </Link>
            <Link href="/pricing" className={link}>
              Plans and prices
            </Link>
            <Link href="/help" className={link}>
              Help and questions
            </Link>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

/** PREMIUM-LOOK-01: what the portal holds, counted from the real book outlines (shared public reads, PUBLIC-CACHE-01),
 * and a slow strip of real chapter names. Published-lesson counts stay in "What is published so far" below. */
async function Stats({ d }: { d: Discovery }) {
  const books = taughtBooks(d.books);
  if (books.length === 0) return null;
  const outlines = await Promise.all(books.map((b) => getBookFor(b.grade, b.subject).catch(() => null)));
  const ok = outlines.flatMap((r) => (r && r.ok ? [r.data] : []));
  const chapters = ok.reduce((n, b) => n + b.chapters.length, 0);
  const topics = ok.reduce((n, b) => n + b.chapters.reduce((m, c) => m + c.topic_count, 0), 0);
  const titles = ok.flatMap((b) => b.chapters.slice(0, 4).map((c) => ({ id: c.id, title: c.title, subject: b.breadcrumb.subject.code })));
  return (
    <div className="space-y-6">
      <section aria-label="What is in the portal" className="grid grid-cols-3 gap-3 sm:gap-4">
        {[
          { n: books.length, l: "books" },
          { n: chapters, l: "chapters" },
          { n: topics, l: "topics" },
        ].map((x) => (
          <div key={x.l} className="glass rounded-card px-3 py-5 text-center sm:py-7">
            <NumberTicker value={x.n} className="block font-display text-3xl font-bold tabular-nums sm:text-5xl" />
            <span className="text-sm text-muted sm:text-base">{x.l}</span>
          </div>
        ))}
      </section>
      {titles.length > 0 && (
        <Marquee label="Some chapters in the portal">
          {titles.map((c) => (
            <span key={c.id} data-subject={subjectKey(c.subject)} className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-4 py-2 text-sm whitespace-nowrap">
              <span className="size-2 rounded-full bg-accent" aria-hidden />
              {c.title}
            </span>
          ))}
        </Marquee>
      )}
    </div>
  );
}
