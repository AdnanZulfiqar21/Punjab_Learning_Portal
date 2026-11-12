import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { BookExercises } from "@portal/contracts";
import { GlassCard } from "@/components/glass-card";
import { Icon, subjectIconName } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { SectionHeader } from "@/components/section-header";
import { Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { bookMocks, partLabel, type BookPart } from "@/lib/book-mocks";
import { practiceChapters } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = {
  title: "Book Mock Test",
  robots: { index: false },
};

type Tab = "full" | "half";

/**
 * BOOK-MOCK-01 (owner, 2026-11-13): Book Mock Test, in two tabs. "Half book mock test": the student picks a book, then
 * a half (e.g. chapters 1–6 or 7–12), and sees its numbered tests. "Full book mock test" does the same for the whole
 * book. Each test is a Board-pattern paper from the chapters' own practice questions, mixed (see lib/book-mocks).
 */
export default function BookMocksPage({ searchParams }: PageProps<"/practice/book-mocks">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Book Mock Test" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · Board paper pattern"
          title="Book Mock Test"
          lead="Full Board-pattern papers from the whole book or from half of it. The questions come from every chapter, mixed. Answer the MCQs here, write the short and long answers, then check them in the Solution paper."
          backdrop={
            <span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />
          }
        />
      </div>
      <Suspense fallback={<SkeletonCards count={6} label="Loading the book mock tests" />}>
        {searchParams.then((sp) => {
          const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : "");
          return <Body tab={one("tab") === "full" ? "full" : "half"} book={one("book")} part={one("part")} />;
        })}
      </Suspense>
    </div>
  );
}

const href = (q: Record<string, string>) => `/practice/book-mocks?${new URLSearchParams(q).toString()}`;

function TabLinks({ items, label }: { items: { key: string; text: string; href: string; active: boolean }[]; label: string }) {
  return (
    <nav aria-label={label}>
      <ul className="glass inline-flex flex-wrap gap-1 rounded-full p-1">
        {items.map((t) => (
          <li key={t.key}>
            <Link
              href={t.href}
              aria-current={t.active ? "page" : undefined}
              className={`inline-flex min-h-11 items-center rounded-full px-5 text-sm transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-accent ${
                t.active ? "bg-accent font-semibold text-white shadow-glass" : "text-foreground hover:text-accent"
              }`}
            >
              {t.text}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

async function Body({ tab, book, part }: { tab: Tab; book: string; part: string }) {
  const [subject, g] = book.split(/-(?=1[12]$)/);
  const grade = Number(g);
  const mocks = subject ? bookMocks(subject, grade) : undefined;
  return (
    <div className="space-y-8">
      <TabLinks
        label="Full book or half book"
        items={[
          { key: "full", text: "Full book mock test", href: href(book ? { tab: "full", book } : { tab: "full" }), active: tab === "full" },
          { key: "half", text: "Half book mock test", href: href(book ? { tab: "half", book } : { tab: "half" }), active: tab === "half" },
        ]}
      />
      {mocks ? <Book tab={tab} subject={subject} grade={grade} part={part} /> : <Books tab={tab} />}
    </div>
  );
}

/** Every book (Class 11 and 12, each subject); the books with tests open, the others say so. */
function Books({ tab }: { tab: Tab }) {
  return (
    <section aria-labelledby="books" className="space-y-4">
      <SectionHeader
        id="books"
        title="Choose a book"
        description={tab === "half" ? "Then choose its first or second half." : "Each test covers the whole book."}
      />
      {[11, 12].map((grade) => (
        <div key={grade} className="space-y-3">
          <h3 className="text-xs font-semibold tracking-[0.15em] text-muted uppercase">{GRADE_LABEL[grade]}</h3>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {SUBJECTS.map(([code, name]) => {
              const m = bookMocks(code, grade);
              const count = m ? (tab === "full" ? m.full.tests : m.halves.reduce((a, h) => a + h.tests, 0)) : 0;
              const inner = (
                <>
                  <span
                    aria-hidden="true"
                    className="flex size-11 shrink-0 items-center justify-center rounded-inner bg-accent-soft text-accent ring-1 ring-accent/20"
                  >
                    <Icon name={subjectIconName(code)} size={20} />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-display font-semibold text-foreground">
                      {GRADE_LABEL[grade]} {name}
                    </span>
                    <span className="text-sm text-muted">{m ? `${count} mock tests` : "Not added yet"}</span>
                  </span>
                  {m && <Icon name="chevron-right" size={18} className="text-muted" />}
                </>
              );
              return (
                <li key={code} data-subject={subjectKey(code)}>
                  {m ? (
                    <Link
                      href={href({ tab, book: `${code}-${grade}` })}
                      className="glass flex min-h-11 items-center gap-3 rounded-card p-4 transition-colors hover:text-accent focus-visible:outline-2 focus-visible:outline-accent"
                    >
                      {inner}
                    </Link>
                  ) : (
                    <div className="glass flex items-center gap-3 rounded-card p-4 opacity-70">{inner}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </section>
  );
}

async function Book({ tab, subject, grade, part: rawPart }: { tab: Tab; subject: string; grade: number; part: string }) {
  const mocks = bookMocks(subject, grade)!;
  const book = `${subject}-${grade}`;
  const name = SUBJECTS.find(([c]) => c === subject)?.[1] ?? subject;
  const user = await currentUser();
  const res = await api<BookExercises>(
    `/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/exercises`,
    user ? { token: user.token } : {},
  );
  const chapters = res.ok ? practiceChapters(res.data) : [];
  const label = res.ok ? res.data.chapter_label : "Chapter";
  const part: BookPart =
    tab === "full" ? mocks.full : (mocks.halves.find((h) => h.key === rawPart) ?? mocks.halves[0]);
  const covered = chapters.filter((c) => c.number >= part.from && c.number <= part.to);
  return (
    <section aria-labelledby="book-tests" className="space-y-6" data-subject={subjectKey(subject)}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <SectionHeader
          id="book-tests"
          title={`${GRADE_LABEL[grade]} ${name}`}
          description={tab === "full" ? "Full book mock tests." : "Half book mock tests: choose a half."}
        />
        <Link href={href({ tab })} className="text-sm font-semibold text-accent hover:underline">
          Choose another book
        </Link>
      </div>
      {tab === "half" && (
        <TabLinks
          label="Which half of the book"
          items={mocks.halves.map((h) => ({
            key: h.key,
            text: partLabel(h, label),
            href: href({ tab, book, part: h.key }),
            active: h.key === part.key,
          }))}
        />
      )}
      {res.ok ? (
        covered.length > 0 && (
          <p className="text-sm text-muted">
            {tab === "full" ? "The whole book" : partLabel(part, label)}:{" "}
            {covered.map((c) => `${c.number}. ${c.title}`).join(" · ")}
          </p>
        )
      ) : (
        <Notice tone="warn" title="Couldn't load the book's chapters">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      )}
      <GlassCard>
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: part.tests }, (_, k) => k + 1).map((n) => (
            <li key={n}>
              <Link
                href={`/practice/book-mocks/paper?grade=${grade}&subject=${subject}&part=${part.key}&n=${n}`}
                className="flex min-h-11 items-center justify-between gap-2 rounded-inner bg-surface-muted px-4 py-2.5 font-semibold text-foreground transition-colors hover:bg-accent-soft hover:text-accent focus-visible:outline-2 focus-visible:outline-accent"
              >
                Mock test {n}
                <Icon name="chevron-right" size={16} className="text-muted" />
              </Link>
            </li>
          ))}
        </ol>
      </GlassCard>
    </section>
  );
}
