"use client";

import { useActionState, useState } from "react";
import { requestExport, type ExportState } from "@/app/actions/exports";

const field = "rounded-lg border border-border bg-surface px-3 py-2";

export function ExportRequestForm({ canAudit }: { canAudit: boolean }) {
  const [state, action, pending] = useActionState<ExportState, FormData>(requestExport, undefined);
  const [kind, setKind] = useState("personal_data");
  return (
    <form action={action} className="space-y-3 rounded-xl border border-border bg-surface p-4" aria-label="Request an export">
      <label className="block space-y-1 text-sm">
        <span className="block font-medium">What to export</span>
        <select name="kind" value={kind} onChange={(e) => setKind(e.target.value)} className={field}>
          <option value="personal_data">Your personal data (JSON)</option>
          {canAudit && <option value="audit_events">Audit trail (CSV, redacted)</option>}
        </select>
      </label>
      {kind === "audit_events" && (
        <div className="flex flex-wrap gap-3 text-sm">
          <label className="space-y-1">
            <span className="block">From (required)</span>
            <input type="datetime-local" name="since" required className={field} />
          </label>
          <label className="space-y-1">
            <span className="block">Until</span>
            <input type="datetime-local" name="until" className={field} />
          </label>
          <label className="space-y-1">
            <span className="block">Action (exact, or a prefix ending in “.”)</span>
            <input type="text" name="action" maxLength={80} className={field} />
          </label>
        </div>
      )}
      <button type="submit" disabled={pending} className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent disabled:opacity-60">
        {pending ? "Requesting…" : "Request export"}
      </button>
      {state?.ok && <p role="status" className="text-sm">Requested. It appears below and is ready in a few moments.</p>}
      {state?.error && (
        <p role="alert" className="text-sm text-danger">
          {state.error}
        </p>
      )}
    </form>
  );
}
