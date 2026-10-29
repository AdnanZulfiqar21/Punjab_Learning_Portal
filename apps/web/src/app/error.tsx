"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";
import { Button } from "@/components/button";
import { CopyDiagnostics } from "@/components/help-link";
import { CenteredCard, PageIcon } from "@/components/learner-pages";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <CenteredCard
      role="alert"
      icon="triangle-alert"
      tone="danger"
      title="We couldn’t load this page"
      lead="The learning service did not respond. Your progress is not affected. Please try again in a moment."
    >
      <div className="flex flex-col items-center gap-3">
        <Button size="lg" onClick={() => retry()} className="w-full sm:w-auto">
          <PageIcon name="rotate-cw" size={18} />
          Try again
        </Button>
        <CopyDiagnostics reference={error.digest} />
        {error.digest && <p className="font-mono text-xs text-muted">Reference: {error.digest}</p>}
      </div>
    </CenteredCard>
  );
}
