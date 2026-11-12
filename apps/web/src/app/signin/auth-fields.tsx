"use client";

import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { LABEL, PageIcon, type PageIconName } from "@/components/learner-pages";

// AUTH-PREMIUM-01: the form parts shared by sign-in, sign-up and the forgotten-password steps.

const INPUT =
  "w-full min-h-[3.125rem] rounded-[14px] border border-border bg-surface pl-11 pr-4 text-foreground outline-none transition duration-150 placeholder:text-muted/70 hover:border-accent/60 focus-visible:border-accent focus-visible:ring-4 focus-visible:ring-accent/15 aria-[invalid=true]:border-danger";

type FieldProps = {
  /** The form field's name. */
  id: string;
  /** The element id, when the caller needs it (e.g. a button that controls the input); otherwise one is made. */
  domId?: string;
  label: string;
  icon: PageIconName;
  hint?: string;
  error?: string;
  trailing?: ReactNode;
} & InputHTMLAttributes<HTMLInputElement>;

// Element ids are unique per page instance (useId), not the field's name: Next keeps the previous page in the document
// while it is hidden, and a second `id="email"` there would take this page's label.
export function AuthField({ id, domId, label, icon, hint, error, trailing, className = "", ...input }: FieldProps) {
  const made = useId();
  const el = domId ?? `${id}-${made}`;
  const described = [hint ? `${el}-hint` : "", error ? `${el}-error` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`space-y-1.5 ${className}`}>
      <label htmlFor={el} className={LABEL}>
        {label}
      </label>
      <div className="relative flex items-center">
        <PageIcon name={icon} size={18} className="pointer-events-none absolute left-3.5 text-muted" />
        <input
          id={el}
          name={id}
          aria-invalid={!!error}
          aria-describedby={described}
          className={`${INPUT} ${trailing ? "pr-12" : ""}`}
          {...input}
        />
        {trailing}
      </div>
      {hint && (
        <p id={`${el}-hint`} className="text-[0.8125rem] text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${el}-error`} className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** Rough guide only (length matters most); the server's only rule is at least 10 characters. */
function strength(v: string): number {
  if (!v) return 0;
  let s = 0;
  if (v.length >= 10) s++;
  if (v.length >= 14) s++;
  if (/[A-Z]/.test(v) && /[a-z]/.test(v)) s++;
  if (/\d|[^\w]/.test(v)) s++;
  return Math.max(1, s);
}

const STRENGTH = ["", "Too weak", "Okay", "Good", "Strong"] as const;

export function PasswordField({
  id,
  label,
  error,
  hint,
  meter = false,
  autoComplete,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  meter?: boolean;
  autoComplete: "current-password" | "new-password";
}) {
  const [shown, setShown] = useState(false);
  const [value, setValue] = useState("");
  const el = `${id}-${useId()}`;
  const s = meter ? strength(value) : 0;
  return (
    <div className="space-y-1.5">
      <AuthField
        id={id}
        domId={el}
        label={label}
        icon="lock"
        type={shown ? "text" : "password"}
        autoComplete={autoComplete}
        required
        minLength={autoComplete === "new-password" ? 10 : undefined}
        error={error}
        hint={meter ? undefined : hint}
        onChange={(e) => setValue(e.currentTarget.value)}
        trailing={
          <button
            type="button"
            // Named "Show"/"Hide" (not "… password") so the field keeps the only "Password" label.
            aria-label={shown ? "Hide" : "Show"}
            aria-controls={el}
            aria-pressed={shown}
            title={shown ? "Hide password" : "Show password"}
            onClick={() => setShown((v) => !v)}
            className="absolute right-1.5 grid size-10 place-items-center rounded-[10px] text-muted transition hover:bg-surface-muted hover:text-foreground"
          >
            <PageIcon name={shown ? "eye-off" : "eye"} size={19} />
          </button>
        }
      />
      {meter && (
        <div className="space-y-1">
          <div className="grid grid-cols-4 gap-1" aria-hidden="true">
            {[1, 2, 3, 4].map((i) => (
              <span
                key={i}
                className={`h-1 rounded-full transition-colors ${
                  i <= s ? (s >= 3 ? "bg-[#0f7a62]" : "bg-[#d48c12]") : "bg-border"
                }`}
              />
            ))}
          </div>
          <p className="text-[0.8125rem] text-muted" aria-live="polite">
            {s ? `${STRENGTH[s]}. ` : ""}
            {hint}
          </p>
        </div>
      )}
    </div>
  );
}

export function SubmitButton({ pending, children, className = "" }: { pending: boolean; children: ReactNode; className?: string }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className={`auth-submit min-h-[3.25rem] w-full rounded-[14px] text-base font-semibold text-white disabled:opacity-70 ${className}`}
    >
      {pending ? "Please wait…" : children}
    </button>
  );
}

export function FormAlert({ error, notice }: { error?: string; notice?: string }) {
  if (error) {
    return (
      <p role="alert" className="rounded-inner border border-danger/30 bg-danger-soft px-4 py-2.5 text-sm">
        {error}
      </p>
    );
  }
  if (notice) {
    return (
      <p role="status" className="rounded-inner border border-accent/30 bg-accent-soft px-4 py-2.5 text-sm">
        {notice}
      </p>
    );
  }
  return null;
}

/** The 6-digit code from an email: large, spaced digits, filled from the SMS/email one-time-code suggestion. */
export function CodeField({ error, defaultValue }: { error?: string; defaultValue?: string }) {
  const el = `code-${useId()}`;
  return (
    <div className="space-y-1.5">
      <label htmlFor={el} className={LABEL}>
        6-digit code
      </label>
      <input
        id={el}
        name="code"
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]*"
        maxLength={6}
        required
        autoFocus
        defaultValue={defaultValue}
        aria-invalid={!!error}
        aria-describedby={error ? `${el}-error` : undefined}
        className="min-h-14 w-full rounded-[14px] border border-border bg-surface px-4 text-center font-display text-[1.75rem] font-semibold tracking-[0.5em] text-foreground outline-none transition hover:border-accent/60 focus-visible:border-accent focus-visible:ring-4 focus-visible:ring-accent/15 aria-[invalid=true]:border-danger"
      />
      {error && (
        <p id={`${el}-error`} className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
