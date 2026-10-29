"use client";

import { useActionState, useState } from "react";
import { requestExport, type ExportState } from "@/app/actions/exports";
import { buttonClasses } from "@/components/button";
import { CardTitle, FIELD, LABEL, PageIcon } from "@/components/learner-pages";

export function ExportRequestForm({ canAudit }: { canAudit: boolean }) {
  const [state, action, pending] = useActionState<ExportState, FormData>(requestExport, undefined);
  const [kind, setKind] = useState("personal_data");
  return (
    <form action={action} className="glass space-y-4 rounded-card p-[22px]" aria-label="Request an export">
      <CardTitle icon="download" level={2}>
        Request an export
      </CardTitle>
      <label className="block space-y-1.5">
        <span className={LABEL}>What to export</span>
        <select name="kind" value={kind} onChange={(e) => setKind(e.target.value)} className={`${FIELD} sm:max-w-sm`}>
          <option value="personal_data">Your personal data (JSON)</option>
          {canAudit && <option value="audit_events">Audit trail (CSV, redacted)</option>}
        </select>
      </label>
      {kind === "audit_events" && (
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="space-y-1.5">
            <span className={LABEL}>From (required)</span>
            <input type="datetime-local" name="since" required className={FIELD} />
          </label>
          <label className="space-y-1.5">
            <span className={LABEL}>Until</span>
            <input type="datetime-local" name="until" className={FIELD} />
          </label>
          <label className="space-y-1.5">
            <span className={LABEL}>Action (exact, or a prefix ending in “.”)</span>
            <input type="text" name="action" maxLength={80} className={FIELD} />
          </label>
        </div>
      )}
      <button type="submit" disabled={pending} className={buttonClasses()}>
        <PageIcon name="download" size={16} />
        {pending ? "Requesting…" : "Request export"}
      </button>
      {state?.ok && (
        <p role="status" className="flex items-center gap-1.5 text-sm">
          <PageIcon name="check" size={16} className="text-ok" />
          Requested. It appears below and is ready in a few moments.
        </p>
      )}
      {state?.error && (
        <p role="alert" className="text-sm text-danger">
          {state.error}
        </p>
      )}
    </form>
  );
}
