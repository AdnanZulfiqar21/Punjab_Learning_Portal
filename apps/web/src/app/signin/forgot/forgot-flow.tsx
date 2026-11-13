"use client";

import Link from "next/link";
import { startTransition, useActionState, useState, type FormEvent } from "react";
import { checkResetCode, finishPasswordReset, requestPasswordReset, type FormState } from "@/app/actions/auth";
import { AuthField, CodeField, FormAlert, PasswordField, SubmitButton } from "../auth-fields";

type Step = "email" | "code" | "password";
const STEPS: { key: Step; label: string }[] = [
  { key: "email", label: "Email" },
  { key: "code", label: "Code" },
  { key: "password", label: "New password" },
];

/** Run an action through a transition so a failed attempt keeps what was typed. */
function submitWith(action: (data: FormData) => void) {
  return (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    startTransition(() => action(data));
  };
}

export function ForgotFlow({ next }: { next: string }) {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [asked, ask, asking] = useActionState<FormState, FormData>(requestPasswordReset, undefined);
  const [checked, check, checking] = useActionState<FormState, FormData>(checkResetCode, undefined);
  const [finished, finish, finishing] = useActionState<FormState, FormData>(finishPasswordReset, undefined);
  const [resent, resend, resending] = useActionState<FormState, FormData>(requestPasswordReset, undefined);

  // A finished step moves the flow on (adjusting state while rendering, when an action's answer changes).
  const [seenAsked, setSeenAsked] = useState(asked);
  if (asked !== seenAsked) {
    setSeenAsked(asked);
    if (asked?.done) {
      setEmail(asked.values?.email ?? "");
      setStep("code");
    }
  }
  const [seenChecked, setSeenChecked] = useState(checked);
  if (checked !== seenChecked) {
    setSeenChecked(checked);
    if (checked?.done) {
      setCode(checked.values?.code ?? "");
      setStep("password");
    }
  }

  const at = STEPS.findIndex((s) => s.key === step);
  return (
    <div className="space-y-5">
      <ol aria-label={`Step ${at + 1} of 3`} className="flex items-center gap-2 text-[0.8125rem] text-muted">
        {STEPS.map((s, i) => (
          <li key={s.key} className="contents">
            {i > 0 && <span aria-hidden="true" className={`h-0.5 flex-1 rounded-full ${i <= at ? "bg-accent" : "bg-border"}`} />}
            <span className={`flex items-center gap-1.5 ${i === at ? "font-semibold text-foreground" : ""}`} aria-current={i === at ? "step" : undefined}>
              <span
                className={`grid size-6 place-items-center rounded-full border text-xs font-semibold ${
                  i <= at ? "border-accent bg-accent text-white" : "border-border"
                }`}
              >
                {i + 1}
              </span>
              <span className={i === at ? "" : "max-sm:sr-only"}>{s.label}</span>
            </span>
          </li>
        ))}
      </ol>

      {step === "email" && (
        <form action={ask} onSubmit={submitWith(ask)} className="space-y-5" noValidate>
          <AuthField
            id="email"
            label="Email"
            icon="mail"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            required
            autoFocus
            defaultValue={asked?.values?.email}
            error={asked?.fieldErrors?.email}
          />
          <FormAlert error={asked?.error} />
          <SubmitButton pending={asking}>Send code</SubmitButton>
        </form>
      )}

      {step === "code" && (
        <>
          <p className="text-sm text-muted">
            If an account uses <strong className="break-all text-foreground" data-testid="reset-email">{email}</strong>, we
            sent a 6-digit code to it. It works for 15 minutes. Check the spam folder too.
          </p>
          <form action={check} onSubmit={submitWith(check)} className="space-y-5" noValidate>
            <input type="hidden" name="email" value={email} />
            <CodeField error={checked?.fieldErrors?.code} />
            <FormAlert error={checked?.error} />
            <SubmitButton pending={checking}>Check code</SubmitButton>
          </form>
          <form action={resend} onSubmit={submitWith(resend)} className="space-y-2 text-center">
            <input type="hidden" name="email" value={email} />
            <button
              type="submit"
              disabled={resending}
              className="min-h-11 w-full rounded-full text-sm font-medium text-accent underline-offset-2 hover:underline"
            >
              {resending ? "Sending…" : "Send a new code"}
            </button>
            {(resent?.notice || resent?.error) && (
              <p role="status" className={`text-sm ${resent.error ? "text-danger" : "text-muted"}`}>
                {resent.error ?? "If you asked less than a minute ago, the code already sent still works."}
              </p>
            )}
          </form>
          <button
            type="button"
            onClick={() => setStep("email")}
            className="min-h-11 w-full text-sm font-medium text-muted underline-offset-2 hover:underline"
          >
            Use a different email
          </button>
        </>
      )}

      {step === "password" && (
        <form action={finish} onSubmit={submitWith(finish)} className="space-y-5" noValidate>
          <input type="hidden" name="email" value={email} />
          <input type="hidden" name="code" value={code} />
          <input type="hidden" name="next" value={next} />
          <p className="text-sm text-muted">Code accepted. Choose a new password for {email}.</p>
          <PasswordField
            id="new_password"
            label="New password"
            autoComplete="new-password"
            meter
            hint="At least 10 characters. A longer phrase is stronger."
            error={finished?.fieldErrors?.new_password}
          />
          <PasswordField
            id="confirm_password"
            label="Type it again"
            autoComplete="new-password"
            error={finished?.fieldErrors?.confirm_password}
          />
          <FormAlert error={finished?.error} />
          {finished?.error && (
            <button
              type="button"
              onClick={() => setStep("code")}
              className="min-h-11 w-full text-sm font-semibold text-accent underline-offset-2 hover:underline"
            >
              Back to the code step
            </button>
          )}
          <SubmitButton pending={finishing}>Save password and sign in</SubmitButton>
          <p className="text-center text-[0.8125rem] text-muted">This also signs you out on every other device.</p>
        </form>
      )}

      <p className="text-center text-sm text-muted">
        Remembered it?{" "}
        <Link href={`/signin?${new URLSearchParams({ next })}`} className="font-medium text-accent underline-offset-2 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
