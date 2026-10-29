"use client";

import { useId, useState, useTransition } from "react";
import type { StaffByEmailIn } from "@portal/contracts";
import { addStaff, removeStaffRole, type StaffResult } from "@/app/actions/staff";
import { ROLE_LABEL, SCOPED_ROLES } from "./roles";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const SUBJECTS: [string, string][] = [
  ["biology", "Biology"],
  ["chemistry", "Chemistry"],
  ["physics", "Physics"],
  ["mathematics", "Mathematics"],
  ["computer_science", "Computer Science"],
];

function Outcome({ result, ok }: { result: StaffResult | null; ok: string }) {
  if (!result) return null;
  return result.ok ? (
    <p role="status" className="text-sm text-ok">
      {ok}
    </p>
  ) : (
    <p role="alert" className="text-sm text-danger">
      {result.error}
    </p>
  );
}

/** Give a role to the account with this exact email. Academic roles are limited to the chosen classes and subjects. */
export function AddStaffForm() {
  const id = useId();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("subject_reviewer");
  const [grades, setGrades] = useState<number[]>([11]);
  const [subjects, setSubjects] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<StaffResult | null>(null);
  const [pending, start] = useTransition();
  const scoped = SCOPED_ROLES.has(role);
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  return (
    <form
      aria-label="Add a staff role"
      className="grid gap-3 rounded-xl border border-border bg-surface p-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          setResult(null);
          const body = { email, role, scope: scoped ? { grades, subjects } : {}, reason } as StaffByEmailIn;
          const out = await addStaff(body);
          setResult(out);
          if (out.ok) {
            setEmail("");
            setReason("");
          }
        });
      }}
    >
      <label className="space-y-1 text-sm" htmlFor={`${id}-email`}>
        <span className="font-medium">Email</span>
        <span className="block text-muted">The exact email the person signed up with.</span>
        <input id={`${id}-email`} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={field} />
      </label>
      <label className="space-y-1 text-sm" htmlFor={`${id}-role`}>
        <span className="font-medium">Role</span>
        <span className="block text-muted">Only what this person needs.</span>
        <select id={`${id}-role`} value={role} onChange={(e) => setRole(e.target.value)} className={field}>
          {Object.entries(ROLE_LABEL).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>
      {scoped && (
        <>
          <fieldset className="space-y-1 text-sm">
            <legend className="font-medium">Classes</legend>
            {[11, 12].map((g) => (
              <label key={g} className="mr-4 inline-flex items-center gap-2">
                <input type="checkbox" checked={grades.includes(g)} onChange={() => setGrades(toggle(grades, g))} />
                Class {g === 11 ? "11" : "12"}
              </label>
            ))}
          </fieldset>
          <fieldset className="space-y-1 text-sm">
            <legend className="font-medium">Subjects</legend>
            {SUBJECTS.map(([v, l]) => (
              <label key={v} className="mr-4 inline-flex items-center gap-2">
                <input type="checkbox" checked={subjects.includes(v)} onChange={() => setSubjects(toggle(subjects, v))} />
                {l}
              </label>
            ))}
          </fieldset>
        </>
      )}
      <label className="space-y-1 text-sm sm:col-span-2" htmlFor={`${id}-reason`}>
        <span className="font-medium">Reason</span>
        <input id={`${id}-reason`} required minLength={5} value={reason} onChange={(e) => setReason(e.target.value)} className={field} />
      </label>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <button
          type="submit"
          disabled={pending || (scoped && (grades.length === 0 || subjects.length === 0))}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
        >
          {pending ? "Adding…" : "Add role"}
        </button>
        <Outcome result={result} ok="Added. It applies from their next request." />
      </div>
    </form>
  );
}

/** Remove one role, with a reason (audited). */
export function RemoveRole({ grantId, label }: { grantId: string; label: string }) {
  const id = useId();
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<StaffResult | null>(null);
  const [pending, start] = useTransition();
  return (
    <form
      aria-label={`Remove ${label}`}
      className="flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => setResult(await removeStaffRole(grantId, reason)));
      }}
    >
      <label htmlFor={`${id}-r`} className="sr-only">
        Reason for removing {label}
      </label>
      <input
        id={`${id}-r`}
        required
        minLength={5}
        placeholder="Reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="rounded-lg border border-border bg-surface px-2 py-1 text-sm"
      />
      <button type="submit" disabled={pending} className="rounded-lg border border-border bg-surface px-3 py-1 text-sm hover:border-accent disabled:opacity-60">
        {pending ? "Removing…" : "Remove"}
      </button>
      <Outcome result={result} ok="Removed." />
    </form>
  );
}
