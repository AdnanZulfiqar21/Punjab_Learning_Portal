"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { startTransition, useActionState, useRef, useState, type FormEvent } from "react";
import { registerWithPassword, signInWithPassword, type FormState } from "@/app/actions/auth";
import { AuthField, FormAlert, PasswordField, SubmitButton } from "./auth-fields";
import { MODE_COPY } from "./mode-copy";

type Mode = keyof typeof MODE_COPY;

/** `?mode=register` opens sign-up; anything else is sign-in. */
function useMode(): Mode {
  return useSearchParams().get("mode") === "register" ? "register" : "signin";
}

/** The page heading and lead, which follow the form's mode. */
export function ModeText({ part }: { part: "title" | "lead" }) {
  return MODE_COPY[useMode()][part];
}

// On a phone, sign-up comes in two short steps (owner 2026-11-12, draft B); on a computer it is one form (draft A).
const STEP_ONE = ["first_name", "surname", "email", "password"] as const;
const TOO_SHORT = "Use at least 10 characters.";

/** AUTH-PASSWORD-01 + AUTH-PREMIUM-01: email + password sign-in, and sign-up that emails a 6-digit code.
 * `devShortcuts` adds the development-only MFA simulation for staff actions. */
export function PasswordForm({ next, devShortcuts }: { next: string; devShortcuts: boolean }) {
  const mode = useMode();
  const register = mode === "register";
  const [step, setStep] = useState<1 | 2>(1);
  const [stepErrors, setStepErrors] = useState<Record<string, string>>({});
  const formRef = useRef<HTMLFormElement>(null);
  const [state, action, pending] = useActionState<FormState, FormData>(
    register ? registerWithPassword : signInWithPassword,
    undefined,
  );
  const errors = { ...(state?.fieldErrors ?? {}), ...stepErrors };
  const typed = state?.values ?? {};

  // A server answer about a first-step field takes the phone back to that step.
  const [seen, setSeen] = useState(state);
  if (state !== seen) {
    setSeen(state);
    if (STEP_ONE.some((k) => k in (state?.fieldErrors ?? {}))) setStep(1);
  }

  // Switching mode only rewrites the address (no reload): the heading updates, and a shared or reloaded link keeps it.
  function setMode(to: Mode) {
    const params = new URLSearchParams(window.location.search);
    if (to === "register") params.set("mode", "register");
    else params.delete("mode");
    setStep(1);
    setStepErrors({});
    window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
  }

  // Submitting through a transition (rather than letting React run the form action) keeps what was typed after a
  // failed attempt, including the password. Before hydration the form still posts to the server action.
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStepErrors({});
    const data = new FormData(e.currentTarget);
    startTransition(() => action(data));
  }

  function toStepTwo() {
    const form = formRef.current;
    if (!form) return;
    const v = (n: string) => String(new FormData(form).get(n) ?? "").trim();
    const errs: Record<string, string> = {};
    if (!v("first_name")) errs.first_name = "Enter your first name.";
    if (!v("surname")) errs.surname = "Enter your surname.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v("email"))) errs.email = "Enter a valid email address.";
    if (String(new FormData(form).get("password") ?? "").length < 10) errs.password = TOO_SHORT;
    setStepErrors(errs);
    if (!Object.keys(errs).length) setStep(2);
  }

  // Classes that hide a step on a phone only; a computer always shows the whole form.
  const one = register && step === 2 ? "max-lg:hidden" : "";
  const two = register && step === 1 ? "max-lg:hidden" : "";
  const forgotHref = `/signin/forgot?${new URLSearchParams({ next })}`;

  return (
    <form ref={formRef} action={action} onSubmit={submit} className="space-y-5" noValidate>
      <input type="hidden" name="next" value={next} />
      <div
        role="tablist"
        aria-label="Sign in or create an account"
        data-mode={mode}
        className="auth-tabs relative grid grid-cols-2 rounded-[14px] border border-border bg-surface-muted p-1"
      >
        <span aria-hidden="true" className="auth-tabs-pill absolute inset-y-1 left-1 w-[calc(50%-4px)] rounded-[10px] bg-surface shadow-sm" />
        {(["signin", "register"] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            onClick={() => mode !== m && setMode(m)}
            className={`relative min-h-11 rounded-[10px] font-semibold transition-colors ${mode === m ? "text-foreground" : "text-muted hover:text-foreground"}`}
          >
            {m === "signin" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>

      {register && (
        <ol aria-label={`Step ${step} of 2`} className="flex items-center gap-2.5 text-[0.8125rem] text-muted lg:hidden">
          {(["Your details", "Contact"] as const).map((label, i) => {
            const on = step === i + 1;
            return (
              <li key={label} className="contents">
                {i === 1 && <span aria-hidden="true" className={`h-0.5 flex-1 rounded-full ${on ? "bg-accent" : "bg-border"}`} />}
                <span className={`flex items-center gap-2 ${on ? "font-semibold text-foreground" : ""}`} aria-current={on ? "step" : undefined}>
                  <span
                    className={`grid size-6 place-items-center rounded-full border text-xs font-semibold ${
                      step >= i + 1 ? "border-accent bg-accent text-white" : "border-border"
                    }`}
                  >
                    {i + 1}
                  </span>
                  {label}
                </span>
              </li>
            );
          })}
        </ol>
      )}

      <div className={`space-y-5 ${one}`}>
        {register && (
          <div className="grid gap-4 sm:grid-cols-2">
            <AuthField
              id="first_name"
              label="First name"
              icon="user"
              autoComplete="given-name"
              autoCapitalize="words"
              maxLength={60}
              required
              defaultValue={typed.first_name}
              error={errors.first_name}
            />
            <AuthField
              id="surname"
              label="Surname"
              icon="user"
              autoComplete="family-name"
              autoCapitalize="words"
              maxLength={60}
              required
              defaultValue={typed.surname}
              error={errors.surname}
            />
          </div>
        )}
        <AuthField
          id="email"
          label="Email"
          icon="mail"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          required
          defaultValue={typed.email}
          error={errors.email}
        />
        <PasswordField
          id="password"
          label="Password"
          autoComplete={register ? "new-password" : "current-password"}
          meter={register}
          hint={register ? "At least 10 characters. A longer phrase is stronger." : undefined}
          error={errors.password}
        />
        {!register && (
          <div className="-mt-2 flex justify-end">
            <Link href={forgotHref} className="text-sm font-semibold text-accent underline-offset-4 hover:underline">
              Forgot password?
            </Link>
          </div>
        )}
      </div>

      {register && (
        <div className={`space-y-5 ${two}`}>
          <div className="grid gap-4 sm:grid-cols-2">
            <AuthField
              id="phone"
              label="Mobile number"
              icon="smartphone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="0300 1234567"
              required
              defaultValue={typed.phone}
              error={errors.phone}
            />
            <AuthField
              id="date_of_birth"
              label="Date of birth"
              icon="calendar"
              type="date"
              autoComplete="bday"
              required
              defaultValue={typed.date_of_birth}
              error={errors.date_of_birth}
            />
          </div>
          <label className="flex min-h-11 cursor-pointer items-start gap-2.5 text-sm text-muted">
            <input
              type="checkbox"
              name="marketing_emails"
              defaultChecked={typed.marketing_emails === "on"}
              className="mt-0.5 size-[18px] shrink-0 accent-[var(--accent)]"
            />
            Send me news about new features and offers. You can stop these at any time.
          </label>
        </div>
      )}

      {!register && devShortcuts && (
        <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-sm text-muted">
          <input type="checkbox" name="mfa" className="size-4 shrink-0 accent-[var(--accent)]" />
          Simulate a multi-factor sign-in (development only, for staff actions)
        </label>
      )}

      <FormAlert error={state?.error} />

      {register && step === 1 && (
        <button type="button" onClick={toStepTwo} className="auth-submit min-h-[3.25rem] w-full rounded-[14px] text-base font-semibold text-white lg:hidden">
          Continue
        </button>
      )}
      <SubmitButton pending={pending} className={two}>
        {register ? "Create account" : "Sign in"}
      </SubmitButton>
      {register && (
        <div className={`flex items-center justify-between gap-3 ${two}`}>
          <button
            type="button"
            onClick={() => setStep(1)}
            className="min-h-11 text-sm font-semibold text-accent underline-offset-4 hover:underline lg:hidden"
          >
            ← Back
          </button>
          <p className="flex-1 text-right text-[0.8125rem] text-muted lg:text-center">
            We&apos;ll email you a 6-digit code to confirm your address.
          </p>
        </div>
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
