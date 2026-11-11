"use client";

import Link from "next/link";
import { useActionState } from "react";
import { resendEmailCode, verifyEmailCode, type FormState } from "@/app/actions/auth";
import { buttonClasses } from "@/components/button";
import { FIELD, LABEL } from "@/components/learner-pages";

export function VerifyForm({ email, next }: { email: string; next: string }) {
  const [state, verify, verifying] = useActionState<FormState, FormData>(verifyEmailCode, undefined);
  const [sent, resend, sending] = useActionState<FormState, FormData>(resendEmailCode, undefined);
  const codeError = state?.fieldErrors?.code;
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted">
        We sent it to <strong className="break-all text-fg" data-testid="pending-email">{email}</strong>. Check the spam
        folder too.
      </p>
      <form action={verify} className="space-y-4" noValidate>
        <input type="hidden" name="next" value={next} />
        <div className="space-y-1.5">
          <label htmlFor="code" className={LABEL}>
            6-digit code
          </label>
          <input
            id="code"
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]*"
            maxLength={6}
            required
            autoFocus
            aria-invalid={!!codeError}
            aria-describedby={codeError ? "code-error" : undefined}
            className={`${FIELD} min-h-12 text-center text-2xl font-semibold tracking-[0.5em]`}
          />
          {codeError && (
            <p id="code-error" className="text-sm text-danger">
              {codeError}
            </p>
          )}
        </div>
        {state?.error && (
          <p role="alert" className="rounded-inner border border-danger/30 bg-danger-soft px-4 py-2.5 text-sm">
            {state.error}
          </p>
        )}
        <button type="submit" disabled={verifying} className={buttonClasses({ size: "lg", className: "w-full" })}>
          {verifying ? "Checking…" : "Confirm email"}
        </button>
      </form>
      <form action={resend} className="space-y-2 text-center">
        <button
          type="submit"
          disabled={sending}
          className="min-h-11 w-full rounded-full text-sm font-medium text-accent underline-offset-2 hover:underline"
        >
          {sending ? "Sending…" : "Send a new code"}
        </button>
        {(sent?.notice || sent?.error) && (
          <p role="status" className={`text-sm ${sent.error ? "text-danger" : "text-muted"}`}>
            {sent.notice ?? sent.error}
          </p>
        )}
      </form>
      <p className="text-center text-sm text-muted">
        Wrong email?{" "}
        <Link href={`/signin?next=${encodeURIComponent(next)}`} className="font-medium text-accent underline-offset-2 hover:underline">
          Start again
        </Link>
      </p>
    </div>
  );
}
