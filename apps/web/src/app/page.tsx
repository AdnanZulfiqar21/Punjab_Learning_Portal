import Link from "next/link";

const SUBJECTS = ["Biology", "Chemistry", "Physics", "Computer Science", "Mathematics"];

export default function Home() {
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
