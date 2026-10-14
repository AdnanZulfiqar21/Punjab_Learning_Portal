"use client";

import { useId, useState, useTransition } from "react";
import type { AccessGrantIn } from "@portal/contracts";
import { grantAccess, revokeAccess, type GrantResult } from "@/app/actions/access-grants";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";

function Outcome({ result, ok }: { result: GrantResult | null; ok: string }) {
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

/** Grant scholarship, promotional or pilot access to the account with this exact email (MFA; audited). */
export function GrantForm() {
  const id = useId();
  const [email, setEmail] = useState("");
  const [source, setSource] = useState<AccessGrantIn["source"]>("pilot");
  const [days, setDays] = useState("30");
  const [units, setUnits] = useState("10");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<GrantResult | null>(null);
  const [pending, start] = useTransition();
  return (
    <form
      aria-label="Grant access"
      className="grid gap-3 rounded-xl border border-border bg-surface p-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          setResult(null);
          const out = await grantAccess({ email, source, days: Number(days), written_units: Number(units), reason, product_code: null });
          setResult(out);
          if (out.ok) {
            setEmail("");
            setReason("");
          }
        });
      }}
    >
      <label className="space-y-1 text-sm" htmlFor={`${id}-email`}>
        <span className="font-medium">Learner email</span>
        <input id={`${id}-email`} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={field} />
      </label>
      <label className="space-y-1 text-sm" htmlFor={`${id}-source`}>
        <span className="font-medium">Kind of access</span>
        <select id={`${id}-source`} value={source} onChange={(e) => setSource(e.target.value as AccessGrantIn["source"])} className={field}>
          <option value="pilot">Pilot (the written-practice pilot)</option>
          <option value="scholarship">Scholarship</option>
          <option value="promotional">Promotional</option>
        </select>
      </label>
      <label className="space-y-1 text-sm" htmlFor={`${id}-days`}>
        <span className="font-medium">Days</span>
        <input id={`${id}-days`} type="number" min={1} max={366} required value={days} onChange={(e) => setDays(e.target.value)} className={field} />
      </label>
      <label className="space-y-1 text-sm" htmlFor={`${id}-units`}>
        <span className="font-medium">Written units</span>
        <input id={`${id}-units`} type="number" min={0} max={500} required value={units} onChange={(e) => setUnits(e.target.value)} className={field} />
      </label>
      <label className="space-y-1 text-sm sm:col-span-2" htmlFor={`${id}-reason`}>
        <span className="font-medium">Reason (kept on the record)</span>
        <textarea id={`${id}-reason`} required minLength={10} maxLength={1000} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={field} />
      </label>
      <div className="space-y-2 sm:col-span-2">
        <button type="submit" disabled={pending} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
          {pending ? "Granting…" : "Grant access"}
        </button>
        <Outcome result={result} ok="Access granted." />
      </div>
    </form>
  );
}

/** Revoke a grant with a reason. Unsealed written tests it funded end; accepted work and results stay (PERMITS-01). */
export function RevokeGrant({ id, label }: { id: string; label: string }) {
  const fieldId = useId();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<GrantResult | null>(null);
  const [pending, start] = useTransition();
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="text-sm text-danger underline underline-offset-2">
        Revoke…
      </button>
    );
  }
  return (
    <form
      aria-label={`Revoke access for ${label}`}
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => setResult(await revokeAccess(id, reason)));
      }}
    >
      <label className="block space-y-1 text-sm" htmlFor={fieldId}>
        <span className="font-medium">Why revoke it? Unsubmitted written tests it paid for will end; submitted work and results stay.</span>
        <input id={fieldId} required minLength={10} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} className={field} />
      </label>
      <div className="flex gap-3">
        <button type="submit" disabled={pending} className="rounded-lg border border-danger px-3 py-1.5 text-sm font-medium text-danger disabled:opacity-60">
          {pending ? "Revoking…" : "Revoke"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-sm text-muted underline">
          Cancel
        </button>
      </div>
      <Outcome result={result} ok="Revoked." />
    </form>
  );
}
