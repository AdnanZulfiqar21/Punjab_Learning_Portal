import type { Metadata } from "next";
import { Suspense } from "react";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { getBookFor, getCatalogue } from "@/lib/api";
import { GRADE_LABEL } from "@/lib/format";
import { requireStaff, StudioForbiddenError, SUBJECT_LABEL } from "@/lib/studio";
import { NewLessonForm, type BookChoice } from "./new-lesson-form";

export const metadata: Metadata = { title: "New draft", robots: { index: false } };

export default function NewLessonPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "New draft" }]} />
      <h1 className="text-2xl font-semibold tracking-tight">New draft</h1>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading books" />}>
        <Form />
      </Suspense>
    </div>
  );
}

async function Form() {
  let me;
  try {
    ({ me } = await requireStaff("/studio/new"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  if (!me.roles.includes("content_author")) {
    return <Notice tone="warn" title="Authors only">Only content authors can start new drafts.</Notice>;
  }
  const catalogue = await getCatalogue();
  if (!catalogue.ok) throw new Error("The catalogue is unavailable.");
  const books: BookChoice[] = [];
  const conflicts: string[] = [];
  for (const g of catalogue.data.grades) {
    for (const { subject, books: bs, edition_conflict } of g.subjects) {
      if (edition_conflict) {
        conflicts.push(`${GRADE_LABEL[g.grade.number]} ${SUBJECT_LABEL[subject.code] ?? subject.name}`);
      }
      if (bs.length === 0) continue;
      const res = await getBookFor(g.grade.number, subject.code);
      if (!res.ok) continue;
      books.push({
        key: `${g.grade.number}:${subject.code}`,
        label: `${GRADE_LABEL[g.grade.number]} ${SUBJECT_LABEL[subject.code] ?? subject.name}`,
        chapters: res.data.chapters.map((c) => ({ id: c.id, label: `Chapter ${c.number}: ${c.title}` })),
      });
    }
  }
  return (
    <>
      {conflicts.length > 0 && (
        <Notice tone="warn" title="More than one edition is effective today">
          {conflicts.join("; ")}. None of those books is offered for a new draft, because the portal does not choose an
          edition. A known edition can still be opened by its link.
        </Notice>
      )}
      <NewLessonForm books={books} />
    </>
  );
}
