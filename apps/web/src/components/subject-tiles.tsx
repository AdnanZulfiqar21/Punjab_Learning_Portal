// DESIGN-01: the subject tiles of the home page (draft C). Each tile is a subject in its own accent with its icon and a
// link to each class's book. Built from the books the API lists (DISCOVERY-01); when the learning service cannot be
// reached it falls back to the four published subjects, linking to the same Learn routes.
import Link from "next/link";
import type { Discovery } from "@portal/contracts";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { TAUGHT_SUBJECTS, taughtBooks } from "@/lib/subjects";
import { GlassCard } from "./glass-card";
import { SubjectIcon } from "./icons";

type Tile = { code: string; name: string; grades: number[] };

const ORDER: readonly string[] = TAUGHT_SUBJECTS;
const FALLBACK: Tile[] = [
  { code: "biology", name: "Biology", grades: [11, 12] },
  { code: "chemistry", name: "Chemistry", grades: [11, 12] },
  { code: "physics", name: "Physics", grades: [11, 12] },
  { code: "computer_science", name: "Computer Science", grades: [11, 12] },
];

function tilesFrom(books: Discovery["books"]): Tile[] {
  const by = new Map<string, Tile>();
  for (const b of taughtBooks(books)) {
    const t = by.get(b.subject) ?? { code: b.subject, name: b.subject_name, grades: [] };
    if (!t.grades.includes(b.grade)) t.grades.push(b.grade);
    by.set(b.subject, t);
  }
  const rank = (c: string) => ORDER.indexOf(c);
  return [...by.values()].map((t) => ({ ...t, grades: t.grades.sort((a, b) => a - b) })).sort((a, b) => rank(a.code) - rank(b.code));
}

export function SubjectTiles({ books, label = "Subjects" }: { books: Discovery["books"] | null; label?: string }) {
  const tiles = books && books.length > 0 ? tilesFrom(books) : FALLBACK;
  return (
    <section aria-label={label}>
      <ul className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {tiles.map((t) => (
          <GlassCard as="li" key={t.code} interactive data-subject={subjectKey(t.code)} className="flex flex-col gap-4">
            <SubjectIcon subject={t.code} />
            <span className="font-display text-[19px] leading-tight font-semibold text-foreground">{t.name}</span>
            <span className="mt-auto flex flex-wrap gap-2">
              {t.grades.map((g) => (
                <Link
                  key={g}
                  href={`/learn/${g}/${t.code}`}
                  aria-label={`${GRADE_LABEL[g] ?? `Class ${g}`} ${t.name}`}
                  className="inline-flex min-h-11 items-center rounded-full border border-border px-3 text-sm font-semibold text-accent hover:border-accent hover:bg-accent-soft"
                >
                  {GRADE_LABEL[g] ?? `Class ${g}`}
                </Link>
              ))}
            </span>
          </GlassCard>
        ))}
      </ul>
    </section>
  );
}
