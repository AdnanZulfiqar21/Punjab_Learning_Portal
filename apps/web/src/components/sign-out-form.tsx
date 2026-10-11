"use client";

// P19.S3.T3 (ISOLATION-01): signing out ends the session on the server and clears everything this browser kept for
// the account before the next person uses it. A plain form post to /account/sign-out (works without JavaScript too).
import { clearDeviceStorage } from "@/lib/device-storage";

export function SignOutForm() {
  return (
    <form method="post" action="/account/sign-out" onSubmit={() => clearDeviceStorage()}>
      <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-danger">
        Sign out of this device
      </button>
      <p className="mt-2 text-sm text-muted">
        This also removes anything kept on this device for your account, such as unsent note drafts.
      </p>
    </form>
  );
}
