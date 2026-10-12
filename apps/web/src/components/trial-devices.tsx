"use client";

// P04.S1.T3: removing a device from the free trial asks once more, because a removed phone or tablet can't rejoin the
// trial by itself (its first-use marker stays recorded; support can review a mistake).
import { useState } from "react";
import { removeTrialDevice } from "@/app/actions/access";

export function RemoveTrialDevice({ id, label }: { id: string; label: string }) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <button
        type="button"
        aria-label={`Remove ${label} from your trial`}
        onClick={() => setAsking(true)}
        className="rounded-lg border border-border px-3 py-1.5 hover:border-danger"
      >
        Remove
      </button>
    );
  }
  return (
    <form action={removeTrialDevice} className="flex flex-wrap items-center gap-2" aria-label={`Remove ${label} from your trial`}>
      <input type="hidden" name="device_id" value={id} />
      <span role="status" className="text-muted">
        It can&apos;t rejoin the trial by itself.
      </span>
      <button type="submit" className="rounded-lg border border-danger px-3 py-1.5 font-medium text-danger">
        Yes, remove
      </button>
      <button type="button" onClick={() => setAsking(false)} className="rounded-lg border border-border px-3 py-1.5">
        Cancel
      </button>
    </form>
  );
}
