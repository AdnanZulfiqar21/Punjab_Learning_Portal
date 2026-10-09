"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";
import { CopyDiagnostics } from "@/components/help-link";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <div role="alert" className="space-y-4 rounded-xl border border-danger/30 bg-danger-soft p-6">
      <h1 className="text-xl font-semibold">We couldn’t load this page</h1>
      <p className="text-muted">
        The learning service did not respond. Your progress is not affected. Please try again in a moment.
      </p>
      {error.digest && <p className="font-mono text-xs text-muted">Reference: {error.digest}</p>}
      <CopyDiagnostics reference={error.digest} />
      <button
        type="button"
        onClick={() => retry()}
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong dark:text-background"
      >
        Try again
      </button>
    </div>
  );
}
