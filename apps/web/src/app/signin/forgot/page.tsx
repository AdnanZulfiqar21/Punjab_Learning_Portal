import type { Metadata } from "next";
import { Suspense } from "react";
import { SkeletonLines } from "@/components/ui";
import { AuthShell } from "../auth-shell";
import { ForgotFlow } from "./forgot-flow";

export const metadata: Metadata = { title: "Reset your password", robots: { index: false } };

/** AUTH-PASSWORD-01 (owner 2026-11-12): forgotten password. Email → 6-digit code → code checked → new password. */
export default function ForgotPasswordPage({ searchParams }: PageProps<"/signin/forgot">) {
  return (
    <AuthShell title="Reset your password" lead="We'll email you a 6-digit code, then you choose a new password.">
      <Suspense fallback={<SkeletonLines lines={3} label="Loading" />}>
        {searchParams.then((sp) => (
          <ForgotFlow next={sameSitePath(sp.next)} />
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
