import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { ContentRelease, StudioItemSummary } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api } from "@/lib/session";
import { getQueue, requireStaff, StudioForbiddenError, SUBJECT_LABEL } from "@/lib/studio";
import { PublishTogether, RollBack } from "./release-forms";

export const metadata: Metadata = { title: "Releases", robots: { index: false } };

const WHEN = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Karachi" });

// P06.S3.T2 (RELEASE-01): a publisher puts several approved items live in one step (a rubric with its written question,
// a passage with its questions, a chapter's lessons). Every item passes today's publication checks in the state the
// release leaves behind, or nothing is published. A release is rolled back as a whole.
export default function ReleasesPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "Releases" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Releases</h1>
        <p className="text-muted">
          Publish approved items together, or none of them. Rolling a release back returns each item to the version learners saw before; nothing is
          deleted and learners&apos; attempts keep the version they used.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading releases" />}>
        <Board />
      </Suspense>
    </div>
  );
}

function detail(i: StudioItemSummary): string {
  const kind = { mcq: "MCQ", written: "Written question", rubric: "Rubric", storyboard: "Storyboard", passage: "Passage" }[i.kind as string] ?? "Lesson";
  const where = `${GRADE_LABEL[i.grade_number]} ${SUBJECT_LABEL[i.subject_code] ?? i.subject_code} · ${i.chapter_title}`;
  return `${kind} · ${where}${i.working_version ? ` · v${i.working_version}` : ""}`;
}

async function Board() {
  let token: string;
  try {
    ({ token } = await requireStaff("/studio/releases"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  const history = await api<ContentRelease[]>("/v1/studio/releases", { token });
  if (!history.ok) {
    return (
      <Notice tone="warn" title="Publishers only">
        {history.problem?.detail ?? "Releases are for publishers in this class and subject, with a multi-factor sign-in."}
      </Notice>
    );
  }
  const approved = await getQueue(token, { state: "approved" });
  return (
    <div className="space-y-8">
      <section aria-labelledby="new-release" className="space-y-3">
        <h2 id="new-release" className="text-lg font-semibold">
          New release
        </h2>
        {approved.length === 0 ? (
          <Notice title="Nothing approved to publish">Items appear here once an independent reviewer has approved them.</Notice>
        ) : (
          <PublishTogether
            items={approved.map((i) => ({ id: i.id, title: i.title, detail: detail(i), live: i.availability === "live" }))}
          />
        )}
      </section>
      <section aria-labelledby="history" className="space-y-3">
        <h2 id="history" className="text-lg font-semibold">
          Recent releases
        </h2>
        {history.data.length === 0 ? (
          <Notice title="No releases yet">Releases you can publish appear here with what each one changed.</Notice>
        ) : (
          <ul className="space-y-3" aria-label="Recent releases">
            {history.data.map((r) => (
              <li key={r.id} className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">{r.label}</p>
                  <Badge tone={r.status === "published" ? "ok" : "warn"}>{r.status === "published" ? "Published" : "Rolled back"}</Badge>
                </div>
                <p className="text-muted">
                  Published {WHEN.format(new Date(r.published_at))} · {r.reason}
                </p>
                {r.rolled_back_at && (
                  <p className="text-muted">
                    Rolled back {WHEN.format(new Date(r.rolled_back_at))} · {r.rollback_reason}
                  </p>
                )}
                <table className="w-full text-left">
                  <caption className="sr-only">Items in {r.label}</caption>
                  <thead className="text-muted">
                    <tr>
                      <th className="pr-4 font-normal">Item</th>
                      <th className="pr-4 font-normal">Released</th>
                      <th className="pr-4 font-normal">Before</th>
                      <th className="font-normal">Learners see now</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.entries.map((e) => (
                      <tr key={e.item_id}>
                        <td className="pr-4">
                          <Link href={`/studio/items/${e.item_id}`} className="text-accent underline-offset-2 hover:underline">
                            {e.title}
                          </Link>
                        </td>
                        <td className="pr-4">v{e.version}</td>
                        <td className="pr-4">{e.previous_version ? `v${e.previous_version}` : "not published"}</td>
                        <td>{e.availability === "live" && e.current_version ? `v${e.current_version}` : "not published"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {r.status === "published" && <RollBack id={r.id} label={r.label} />}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
