"use client";

import { useActionState, useState } from "react";
import { registerWithPassword, signInWithPassword, type FormState } from "@/app/actions/auth";
import { buttonClasses } from "@/components/button";
import { FIELD, LABEL } from "@/components/learner-pages";

export function DevPasswordForm({ next }: { next: string }) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [state, action, pending] = useActionState<FormState, FormData>(
    mode === "signin" ? signInWithPassword : registerWithPassword,
    undefined,
  );
  return (
    <form action={action} className="space-y-4" noValidate>
      <input type="hidden" name="next" value={next} />
      <div className="space-y-1.5">
        <label htmlFor="email" className={LABEL}>
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          aria-invalid={!!state?.fieldErrors?.email}
          aria-describedby={state?.fieldErrors?.email ? "email-error" : undefined}
          className={`${FIELD} min-h-12`}
        />
        {state?.fieldErrors?.email && (
          <p id="email-error" className="text-sm text-danger">
            {state.fieldErrors.email}
          </p>
        )}
      </div>
      <div className="space-y-1.5">
        <label htmlFor="password" className={LABEL}>
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete={mode === "signin" ? "current-password" : "new-password"}
          required
          minLength={mode === "register" ? 10 : undefined}
          aria-invalid={!!state?.fieldErrors?.password}
          aria-describedby={state?.fieldErrors?.password ? "password-error" : undefined}
          className={`${FIELD} min-h-12`}
        />
        {state?.fieldErrors?.password && (
          <p id="password-error" className="text-sm text-danger">
            {state.fieldErrors.password}
          </p>
        )}
      </div>
      {mode === "signin" && (
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
      <button
        type="submit"
        disabled={pending}
        className={buttonClasses({ size: "lg", className: "w-full" })}
      >
        {pending ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
      </button>
      <button
        type="button"
        onClick={() => setMode(mode === "signin" ? "register" : "signin")}
        className="min-h-11 w-full rounded-full text-sm font-medium text-accent underline-offset-2 hover:underline"
      >
        {mode === "signin" ? "New here? Create an account" : "Already have an account? Sign in"}
      </button>
    </form>
  );
}
