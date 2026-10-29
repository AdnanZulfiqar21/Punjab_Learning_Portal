"use client";

import { buttonClasses } from "@/components/button";
import { PracticeIcon } from "@/components/practice-ui";
import { useRef, useState, useTransition } from "react";
import { startMock } from "@/app/actions/practice";

const newKey = () => crypto.randomUUID().replaceAll("-", "");

export function StartMock({ code }: { code: string }) {
  // One idempotency key per press: a double click or retry returns the same mock instead of building a second one.
  const key = useRef<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-1">
      <button
        type="button"
        disabled={pending}
        onClick={() =>
          start(async () => {
            key.current ??= newKey();
            const out = await startMock(code, key.current);
            if (out?.error) {
              key.current = null;
              setError(out.error);
            }
          })
        }
        className={buttonClasses()}
      >
        <PracticeIcon name="timer" size={18} />
        {pending ? "Preparing your mock…" : "Start mock (timed)"}
      </button>
      {error && (
        <p role="alert" className="rounded-inner border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {error}
        </p>
      )}
    </div>
  );
}
