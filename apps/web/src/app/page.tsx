import Link from "next/link";
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
import { getDiscovery } from "@/lib/api";
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
  if (!user) return <Welcome d={await discovery()} />;
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
function Welcome({ d }: { d: Discovery | null }) {
  const lessons = d?.books.reduce((n, b) => n + b.live_lessons, 0) ?? 0;
  const previews = d?.books.reduce((n, b) => n + b.preview_lessons, 0) ?? 0;
  const outlineOnly = d?.books.filter((b) => b.state === "not_yet_published").length ?? 0;
  const link = "font-medium text-accent underline underline-offset-2";
  return (
    <div className="space-y-12">
      <PageHero
        eyebrow="Class 11 · Class 12"
        title={
          <>
            Learn your Punjab textbook <br className="hidden sm:inline" />
            the easy way.
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

      <SubjectTiles books={d?.books ?? null} />

      <section aria-labelledby="features-heading">
        <h2 id="features-heading" className="sr-only">
          How you study here
        </h2>
        <ul className="grid gap-4 md:grid-cols-3">
          {FEATURES.map((f) => (
            <GlassCard as="li" key={f.title} className="space-y-1.5">
              <p className="flex items-center gap-1.5 text-sm text-muted">
                <Icon name={f.icon} size={16} className="text-accent" />
                {f.label}
              </p>
              <h3 className="font-display text-lg font-semibold">{f.title}</h3>
              <p className="text-[15px] text-muted">{f.text}</p>
            </GlassCard>
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
