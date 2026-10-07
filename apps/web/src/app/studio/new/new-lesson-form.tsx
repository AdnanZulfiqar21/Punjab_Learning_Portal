"use client";

import { useActionState, useState, useTransition } from "react";
import { createItem } from "@/app/actions/studio";
import { chapterTopics, type TopicChoice } from "@/app/actions/studio-read";

export type BookChoice = { key: string; label: string; chapters: { id: string; label: string }[] };

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2.5";

export function NewLessonForm({ books }: { books: BookChoice[] }) {
  const [state, action, pending] = useActionState(createItem, undefined);
  const [bookKey, setBookKey] = useState(books[0]?.key ?? "");
  const [chapterId, setChapterId] = useState("");
  const [topics, setTopics] = useState<TopicChoice[]>([]);
  const [loadingTopics, startLoading] = useTransition();
  const book = books.find((b) => b.key === bookKey);

  function chooseChapter(id: string) {
    setChapterId(id);
    setTopics([]);
    if (id) startLoading(async () => setTopics(await chapterTopics(id)));
  }

  return (
    <form action={action} className="space-y-5">
      <fieldset className="space-y-2">
        <legend className="font-medium">What are you writing?</legend>
        <div className="flex flex-wrap gap-3">
          <label className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2">
            <input type="radio" name="kind" value="lesson" defaultChecked /> Lesson
          </label>
          <label className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2">
            <input type="radio" name="kind" value="mcq" /> Multiple-choice question
          </label>
        </div>
      </fieldset>
      <div className="space-y-1">
        <label htmlFor="book" className="font-medium">
          Book
        </label>
        <select
          id="book"
          value={bookKey}
          onChange={(e) => {
            setBookKey(e.target.value);
            chooseChapter("");
          }}
          className={field}
        >
          {books.map((b) => (
            <option key={b.key} value={b.key}>
              {b.label}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <label htmlFor="chapter_id" className="font-medium">
          Chapter
        </label>
        <select id="chapter_id" name="chapter_id" value={chapterId} onChange={(e) => chooseChapter(e.target.value)} className={field} required>
          <option value="">Choose a chapter</option>
          {book?.chapters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <label htmlFor="topic_id" className="font-medium">
          Topic <span className="font-normal text-muted">(optional)</span>
        </label>
        <select id="topic_id" name="topic_id" className={field} disabled={!chapterId || loadingTopics}>
          <option value="">Whole chapter</option>
          {topics.map((t) => (
            <option key={t.id} value={t.id}>
              {" ".repeat(Math.max(0, t.depth - 1) * 3)}
              {t.number ? `${t.number} ` : ""}
              {t.title}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <label htmlFor="title" className="font-medium">
          Title
        </label>
        <input id="title" name="title" required minLength={3} maxLength={200} className={field} />
      </div>
      {state?.error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Creating…" : "Create draft"}
      </button>
    </form>
  );
}
