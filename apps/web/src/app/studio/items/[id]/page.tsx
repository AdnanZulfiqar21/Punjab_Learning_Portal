import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { getHistory, getItem, requireStaff, StudioForbiddenError } from "@/lib/studio";
import { AddRubric } from "./add-rubric";
import type { QuestionVersionChoice } from "./written-editor";
import { Workspace } from "./workspace";

export const metadata: Metadata = { title: "Studio item", robots: { index: false } };

export default function StudioItemPage({ params }: PageProps<"/studio/items/[id]">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "Item" }]} />
      <Suspense fallback={<SkeletonLines lines={8} label="Loading the item" />}>
        {params.then(({ id }) => (
          <Item id={id} />
        ))}
      </Suspense>
    </div>
  );
}

async function Item({ id }: { id: string }) {
  let auth;
  try {
    auth = await requireStaff(`/studio/items/${id}`);
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const item = await getItem(auth.token, id);
  if (!item) notFound();
  const history = await getHistory(auth.token, id);
  // A rubric marks one version of its written question: offer that question's versions to choose from.
  let questionVersions: QuestionVersionChoice[] = [];
  if (item.kind === "rubric" && item.parent_item_id) {
    const parent = await getItem(auth.token, item.parent_item_id);
    questionVersions = [parent?.working, parent?.published]
      .filter((v): v is NonNullable<typeof v> => !!v)
      .map((v) => ({ id: v.id, number: v.number, status: v.status, body: v.body }));
  }
  // Remount the client workspace whenever the server state changes, so it never edits stale data.
  const key = `${item.id}:${item.state}:${item.availability}:${item.working?.number}:${item.working?.revision}`;
  return (
    <div className="space-y-4">
      {item.kind === "written" && auth.me.roles.includes("content_author") && <AddRubric questionId={item.id} title={item.title} />}
      {item.kind === "rubric" && item.parent_item_id && (
        <Link href={`/studio/items/${item.parent_item_id}`} className="text-sm text-accent underline-offset-2 hover:underline">
          ← The question this rubric marks
        </Link>
      )}
      <Workspace key={key} item={item} history={history} myId={auth.me.id} questionVersions={questionVersions} />
    </div>
  );
}
