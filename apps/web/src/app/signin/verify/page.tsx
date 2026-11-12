import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { SkeletonLines } from "@/components/ui";
import { pendingEmail } from "@/lib/session";
import { AuthShell } from "../auth-shell";
import { VerifyForm } from "./verify-form";

export const metadata: Metadata = { title: "Confirm your email", robots: { index: false } };

/** AUTH-PASSWORD-01: enter the 6-digit code emailed at sign-up. The address comes from an HTTP-only cookie. */
export default function VerifyEmailPage({ searchParams }: PageProps<"/signin/verify">) {
  return (
    <AuthShell title="Confirm your email" lead="Enter the 6-digit code we emailed you. It works for 15 minutes.">
      <Suspense fallback={<SkeletonLines lines={3} label="Loading" />}>
        {searchParams.then((sp) => (
          <Pending next={sameSitePath(sp.next)} />
        ))}
      </Suspense>
    </AuthShell>
  );
}

/** Only same-site relative paths (the same rule as the sign-in actions); never an open redirect. */
function sameSitePath(next: unknown): string {
  const n = typeof next === "string" ? next : "";
  if (/[\u0000-\u001f\u007f\\]/.test(n)) return "/account";
  return /^\/(?!\/)/.test(n) ? n : "/account";
}

async function Pending({ next }: { next: string }) {
  const email = await pendingEmail();
  if (!email) redirect(`/signin?next=${encodeURIComponent(next)}`);
  return <VerifyForm email={email} next={next} />;
}
