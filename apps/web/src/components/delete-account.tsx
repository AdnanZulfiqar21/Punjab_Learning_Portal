"use client";

import { useState, useTransition } from "react";
import { requestDeletion } from "@/app/actions/privacy";

/** P18.S3.T2: ask for the account to be deleted. Support handles it under the retention policy; nothing is erased here. */
export function DeleteAccount() {
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-2">
      <label htmlFor="delete-email" className="block text-sm font-medium">
        Type your email address to confirm
      </label>
      <input id="delete-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
      <label htmlFor="delete-reason" className="block text-sm font-medium">
        Reason <span className="font-normal text-muted">(optional)</span>
      </label>
      <textarea id="delete-reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={1000} className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
      <button
        type="button"
        disabled={pending || !email.trim()}
        onClick={() => start(async () => setResult(await requestDeletion(email.trim(), reason.trim())))}
        className="rounded-lg border border-danger/40 bg-surface px-4 py-2 font-medium text-danger hover:bg-danger-soft disabled:opacity-60"
      >
        {pending ? "Sending…" : "Ask us to delete my account"}
      </button>
      {result && (
        <p role={result.ok ? "status" : "alert"} className={`text-sm ${result.ok ? "" : "text-danger"}`}>
          {result.message}
        </p>
      )}
    </div>
  );
}
