import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { StudioItemSummary } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import {
  AVAILABILITY_LABEL,
  getQueue,
  requireStaff,
  STATE_LABEL,
  StudioForbiddenError,
  SUBJECT_LABEL,
  type QueueFilters,
} from "@/lib/studio";

export const metadata: Metadata = { title: "Content studio", robots: { index: false } };

export default function StudioPage({ searchParams }: PageProps<"/studio">) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Content studio</h1>
          <p className="text-muted">Drafts stay private until an independent reviewer approves them and they are published.</p>
        </div>
        <div className="flex gap-2">
        <Link href="/studio/support" className="rounded-lg border border-border bg-surface px-4 py-2.5 font-medium hover:border-accent">
          Support queue
        </Link>
        <Link href="/studio/marking" className="rounded-lg border border-border bg-surface px-4 py-2.5 font-medium hover:border-accent">
          Written marking
        </Link>
        <Link href="/studio/adjudications" className="rounded-lg border border-border bg-surface px-4 py-2.5 font-medium hover:border-accent">
          Rubric corrections
        </Link>
        <Link href="/studio/imports" className="rounded-lg border border-border bg-surface px-4 py-2.5 font-medium hover:border-accent">
          Import
        </Link>
        <form action="/studio/export" method="get" className="flex items-center gap-1" aria-label="Export content">
          <select name="grade" aria-label="Export class" className="rounded-lg border border-border bg-surface px-2 py-2.5">
            <option value="11">XI</option>
            <option value="12">XII</option>
          </select>
          <select name="subject" aria-label="Export subject" className="rounded-lg border border-border bg-surface px-2 py-2.5">
            <option value="biology">Biology</option>
            <option value="chemistry">Chemistry</option>
            <option value="physics">Physics</option>
            <option value="computer_science">Computer Science</option>
            <option value="mathematics">Mathematics</option>
          </select>
          <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2.5 font-medium hover:border-accent">
            Export
          </button>
        </form>
        <Link
          href="/studio/new"
          className="rounded-lg bg-accent px-4 py-2.5 font-medium text-white hover:bg-accent-strong dark:text-background"
        >
          New draft
        </Link>
        </div>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading the work queue" />}>
        {searchParams.then((sp) => (
          <Queue filters={pick(sp)} />
        ))}
      </Suspense>
    </div>
  );
}

function pick(sp: Record<string, string | string[] | undefined>): QueueFilters {
  const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : undefined);
  return { state: one("state"), availability: one("availability"), grade: one("grade"), subject: one("subject"), mine: one("mine") };
}

async function Queue({ filters }: { filters: QueueFilters }) {
  let token: string;
  try {
    ({ token } = await requireStaff("/studio"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) {
      return <Notice tone="warn" title="Staff only">{e.message} Ask an administrator if you need access.</Notice>;
    }
    throw e;
  }
  const items = await getQueue(token, filters);
  return (
    <div className="space-y-4">
      <Filters filters={filters} />
      {items.length === 0 ? (
        <Notice title="Nothing here yet">No items match these filters.</Notice>
      ) : (
        <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Work queue">
          {items.map((i) => (
            <QueueRow key={i.id} item={i} />
          ))}
        </ul>
      )}
    </div>
  );
}

const STATE_TONE: Record<string, "info" | "warn" | "ok"> = {
  draft: "info",
  submitted: "info",
  changes_requested: "warn",
  approved: "ok",
  published: "ok",
};

function age(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  return days <= 0 ? "today" : days === 1 ? "1 day ago" : `${days} days ago`;
}

function QueueRow({ item: i }: { item: StudioItemSummary }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
      <div className="min-w-0 space-y-1">
        <Link href={`/studio/items/${i.id}`} className="font-medium text-accent underline-offset-2 hover:underline">
          {i.title}
        </Link>
        <p className="text-sm text-muted">
          {GRADE_LABEL[i.grade_number]} {SUBJECT_LABEL[i.subject_code] ?? i.subject_code} · {i.chapter_title}
          {i.topic_title ? ` · ${i.topic_title}` : ""}
        </p>
        <p className="text-xs text-muted">
          By {i.created_by ?? "unknown"} · reviewer {i.assigned_reviewer ?? "unassigned"} · updated {age(i.updated_at)}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge>{{ mcq: "MCQ", written: "Written", rubric: "Rubric", storyboard: "Storyboard" }[i.kind as string] ?? "Lesson"}</Badge>
        <Badge tone={STATE_TONE[i.state]}>
          {STATE_LABEL[i.state]}
          {i.working_version ? ` · v${i.working_version}` : ""}
        </Badge>
        {i.availability !== "unpublished" && (
          <Badge tone={i.availability === "live" ? "ok" : "warn"}>{AVAILABILITY_LABEL[i.availability]}</Badge>
        )}
        {i.open_feedback > 0 && <Badge tone="warn">{i.open_feedback} open feedback</Badge>}
      </div>
    </li>
  );
}

const select = "rounded-lg border border-border bg-surface px-3 py-2 text-sm";

function Filters({ filters }: { filters: QueueFilters }) {
  return (
    <form method="get" className="flex flex-wrap items-end gap-3" aria-label="Filter the queue">
      <label className="space-y-1 text-sm">
        <span className="block text-muted">State</span>
        <select name="state" defaultValue={filters.state ?? ""} className={select}>
          <option value="">Any</option>
          {Object.entries(STATE_LABEL).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1 text-sm">
        <span className="block text-muted">Class</span>
        <select name="grade" defaultValue={filters.grade ?? ""} className={select}>
          <option value="">Both</option>
          <option value="11">Class XI</option>
          <option value="12">Class XII</option>
        </select>
      </label>
      <label className="space-y-1 text-sm">
        <span className="block text-muted">Subject</span>
        <select name="subject" defaultValue={filters.subject ?? ""} className={select}>
          <option value="">All</option>
          {Object.entries(SUBJECT_LABEL).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 pb-2 text-sm">
        <input type="checkbox" name="mine" value="true" defaultChecked={filters.mine === "true"} />
        Mine only
      </label>
      <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium hover:border-accent">
        Apply
      </button>
    </form>
  );
}
