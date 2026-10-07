import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { getHistory, getItem, requireStaff, StudioForbiddenError } from "@/lib/studio";
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
  // Remount the client workspace whenever the server state changes, so it never edits stale data.
  const key = `${item.id}:${item.state}:${item.availability}:${item.working?.number}:${item.working?.revision}`;
  return <Workspace key={key} item={item} history={history} myId={auth.me.id} />;
}
