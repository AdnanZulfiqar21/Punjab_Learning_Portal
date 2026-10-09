"use client";

import { useActionState } from "react";
import type { NotificationPreferences as Prefs } from "@portal/contracts";
import { savePreferences, type PreferencesState } from "@/app/actions/notifications";

// P15.S1.T3: channels, optional categories, the timezone used to show times, and quiet hours (urgent notices, such
// as a teacher's request with a deadline, still arrive). Service notices always appear in the inbox.
export function NotificationPreferences({ initial }: { initial: Prefs }) {
  const [state, action, pending] = useActionState<PreferencesState, FormData>(savePreferences, undefined);
  const box = (name: keyof Prefs, label: string) => (
    <label className="flex items-center gap-2">
      <input type="checkbox" name={name} defaultChecked={Boolean(initial[name])} />
      {label}
    </label>
  );
  return (
    <form action={action} className="space-y-3 text-sm">
      {box("email_enabled", "Email me")}
      {box("push_enabled", "Send notifications to my phone (when the app supports it)")}
      {box("reminders_enabled", "Study reminders")}
      {box("promotional_opt_in", "News about new content (optional)")}
      <div className="flex flex-wrap gap-4">
        <label className="space-y-1">
          <span className="block">Timezone</span>
          <input name="timezone" defaultValue={initial.timezone} className="rounded border border-border bg-surface px-2 py-1" maxLength={60} />
        </label>
        <label className="space-y-1">
          <span className="block">Quiet from</span>
          <input type="time" name="quiet_start" defaultValue={initial.quiet_start} className="rounded border border-border bg-surface px-2 py-1" />
        </label>
        <label className="space-y-1">
          <span className="block">Quiet until</span>
          <input type="time" name="quiet_end" defaultValue={initial.quiet_end} className="rounded border border-border bg-surface px-2 py-1" />
        </label>
      </div>
      {state?.error && (
        <p role="alert" className="text-danger">
          {state.error}
        </p>
      )}
      {state?.ok && <p role="status">Saved.</p>}
      <button type="submit" disabled={pending} className="rounded-lg border border-border px-4 py-2 font-medium disabled:opacity-60">
        {pending ? "Saving…" : "Save notification settings"}
      </button>
    </form>
  );
}
