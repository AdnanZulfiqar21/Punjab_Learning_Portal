"use client";

import Link from "next/link";
import { useActionState } from "react";
import { resendEmailCode, verifyEmailCode, type FormState } from "@/app/actions/auth";
import { CodeField, FormAlert, SubmitButton } from "../auth-fields";

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
        <CodeField error={codeError} />
        <FormAlert error={state?.error} />
        <SubmitButton pending={verifying}>Confirm email</SubmitButton>
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
        <Link href={`/signin?${new URLSearchParams({ mode: "register", next })}`} className="font-medium text-accent underline-offset-2 hover:underline">
          Start again
        </Link>
      </p>
    </div>
  );
}
