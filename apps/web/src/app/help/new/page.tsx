import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { Breadcrumbs, SkeletonLines } from "@/components/ui";
import { currentUser } from "@/lib/session";
import { NewTicketForm } from "./new-ticket-form";

export const metadata: Metadata = { title: "New help request", robots: { index: false } };

export default function NewTicketPage({ searchParams }: PageProps<"/help/new">) {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Breadcrumbs items={[{ href: "/help", label: "Help" }, { label: "New request" }]} />
      <h1 className="text-2xl font-semibold tracking-tight">How can we help?</h1>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading" />}>
        {searchParams.then(async (sp) => {
          const user = await currentUser();
          if (!user) redirect("/help/new");
          const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : "");
          return <NewTicketForm category={one("category") || "technical"} refKind={one("kind")} refId={one("id")} refPosition={one("position")} />;
        })}
      </Suspense>
    </div>
  );
}
