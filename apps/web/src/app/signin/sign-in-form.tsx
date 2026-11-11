"use client";

import { useActionState, useState } from "react";
import { registerWithPassword, signInWithPassword, type FormState } from "@/app/actions/auth";
import { buttonClasses } from "@/components/button";
import { FIELD, LABEL } from "@/components/learner-pages";

function Field({
  id,
  label,
  hint,
  error,
  ...input
}: { id: string; label: string; hint?: string; error?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  const described = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-muted">
          {hint}
        </p>
      )}
      <input id={id} name={id} aria-invalid={!!error} aria-describedby={described} className={`${FIELD} min-h-12`} {...input} />
      {error && (
        <p id={`${id}-error`} className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** AUTH-PASSWORD-01: email + password sign-in, and sign-up that emails a 6-digit code. `devShortcuts` adds the
 * development-only MFA simulation for staff actions. */
export function PasswordForm({ next, devShortcuts }: { next: string; devShortcuts: boolean }) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [state, action, pending] = useActionState<FormState, FormData>(
    mode === "signin" ? signInWithPassword : registerWithPassword,
    undefined,
  );
  const register = mode === "register";
  const errors = state?.fieldErrors ?? {};
  return (
    <form action={action} className="space-y-4" noValidate>
      <input type="hidden" name="next" value={next} />
      <Field id="email" label="Email" type="email" autoComplete="email" required error={errors.email} />
      <Field
        id="password"
        label="Password"
        type="password"
        autoComplete={register ? "new-password" : "current-password"}
        required
        minLength={register ? 10 : undefined}
        hint={register ? "At least 10 characters." : undefined}
        error={errors.password}
      />
      {register && (
        <>
          <Field
            id="phone"
            label="Mobile number"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            placeholder="0300 1234567"
            required
            error={errors.phone}
          />
          <Field id="date_of_birth" label="Date of birth" type="date" autoComplete="bday" required error={errors.date_of_birth} />
          <label className="flex min-h-11 cursor-pointer items-start gap-2.5 text-sm text-muted">
            <input type="checkbox" name="marketing_emails" className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]" />
            Email me about new features and offers. You can stop these at any time.
          </label>
        </>
      )}
      {!register && devShortcuts && (
        <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-sm text-muted">
          <input type="checkbox" name="mfa" className="size-4 shrink-0 accent-[var(--accent)]" />
          Simulate a multi-factor sign-in (development only, for staff actions)
        </label>
      )}
      {state?.error && (
        <p role="alert" className="rounded-inner border border-danger/30 bg-danger-soft px-4 py-2.5 text-sm">
          {state.error}
        </p>
      )}
      <button type="submit" disabled={pending} className={buttonClasses({ size: "lg", className: "w-full" })}>
        {pending ? "Please wait…" : register ? "Create account" : "Sign in"}
      </button>
      {register && (
        <p className="text-center text-sm text-muted">We&apos;ll email you a 6-digit code to confirm your address.</p>
      )}
      <button
        type="button"
        onClick={() => setMode(register ? "signin" : "register")}
        className="min-h-11 w-full rounded-full text-sm font-medium text-accent underline-offset-2 hover:underline"
      >
        {register ? "Already have an account? Sign in" : "New here? Create an account"}
      </button>
    </form>
  );
}
