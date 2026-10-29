import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { IconTile } from "@/components/learner-pages";
import { Breadcrumbs, SkeletonLines } from "@/components/ui";
import { currentUser } from "@/lib/session";
import { NewTicketForm } from "./new-ticket-form";

export const metadata: Metadata = { title: "New help request", robots: { index: false } };

export default function NewTicketPage({ searchParams }: PageProps<"/help/new">) {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Breadcrumbs items={[{ href: "/help", label: "Help" }, { label: "New request" }]} />
      <div className="glass space-y-6 rounded-card px-5 py-7 sm:px-9 sm:py-9">
      <div className="flex items-center gap-4">
        <IconTile icon="circle-help" size={52} />
        <div className="space-y-1">
          <h1 className="font-display text-[28px] leading-9 font-bold tracking-tight sm:text-[32px] sm:leading-10">How can we help?</h1>
          <p className="text-sm text-muted">Your request and our replies appear on your Help page.</p>
        </div>
      </div>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading" />}>
        {searchParams.then(async (sp) => {
          const user = await currentUser();
          const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : "");
          if (!user) {
            const back = new URLSearchParams(Object.entries({ category: one("category"), kind: one("kind"), id: one("id"), position: one("position") }).filter(([, v]) => v));
            redirect(`/signin?next=${encodeURIComponent(`/help/new${back.size ? `?${back.toString()}` : ""}`)}`); // never back to itself: that looped
          }
          return <NewTicketForm category={one("category") || "technical"} refKind={one("kind")} refId={one("id")} refPosition={one("position")} />;
        })}
      </Suspense>
      </div>
    </div>
  );
}
