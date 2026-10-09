import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { currentUser } from "@/lib/session";
import { CatalogueManager } from "./manager";

export const metadata: Metadata = { title: "Catalogue", robots: { index: false } };

export default function CataloguePage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Catalogue" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Catalogue</h1>
        <p className="text-muted">
          Classes, subjects, chapters and topics come from the textbooks through the reviewed catalogue file. Change that file, then preview here: you&apos;ll see every chapter
          and topic that would be added, renamed, moved, reordered or retired, and the content that depends on them, before anything is applied. Nothing is deleted; retired
          structure is kept for history.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={4} label="Checking your access" />}>
        <Gate />
      </Suspense>
    </div>
  );
}

async function Gate() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/catalogue");
  if (!user.me.roles.includes("owner_admin"))
    return (
      <Notice tone="warn" title="Owner and admins only">
        Only the owner or an administrator can change the catalogue.
      </Notice>
    );
  if (!user.me.mfa_session)
    return (
      <Notice tone="warn" title="Multi-factor sign-in needed">
        Sign in again with multi-factor authentication to preview or apply catalogue changes.
      </Notice>
    );
  return <CatalogueManager />;
}
