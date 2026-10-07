"use client";

import { useActionState, useState } from "react";
import { registerWithPassword, signInWithPassword, type FormState } from "@/app/actions/auth";

export function DevPasswordForm({ next }: { next: string }) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [state, action, pending] = useActionState<FormState, FormData>(
    mode === "signin" ? signInWithPassword : registerWithPassword,
    undefined,
  );
  return (
    <form action={action} className="space-y-4" noValidate>
      <input type="hidden" name="next" value={next} />
      <div className="space-y-1">
        <label htmlFor="email" className="block text-sm font-medium">
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
          className="w-full rounded-lg border border-border bg-surface px-4 py-3"
        />
        {state?.fieldErrors?.email && (
          <p id="email-error" className="text-sm text-danger">
            {state.fieldErrors.email}
          </p>
        )}
      </div>
      <div className="space-y-1">
        <label htmlFor="password" className="block text-sm font-medium">
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
          className="w-full rounded-lg border border-border bg-surface px-4 py-3"
        />
        {state?.fieldErrors?.password && (
          <p id="password-error" className="text-sm text-danger">
            {state.fieldErrors.password}
          </p>
        )}
      </div>
      {mode === "signin" && (
        <label className="flex items-center gap-2 text-sm text-muted">
          <input type="checkbox" name="mfa" />
          Simulate a multi-factor sign-in (development only, for staff actions)
        </label>
      )}
      {state?.error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
      </button>
      <button
        type="button"
        onClick={() => setMode(mode === "signin" ? "register" : "signin")}
        className="w-full text-sm text-accent underline-offset-2 hover:underline"
      >
        {mode === "signin" ? "New here? Create an account" : "Already have an account? Sign in"}
      </button>
    </form>
  );
}
