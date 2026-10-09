"use client";

import Link from "next/link";
import { useState } from "react";

// P15.S2.T2: contextual help from a failure state, and safe diagnostics a learner can paste into a help request.
// The diagnostics never include tokens, cookies, answers or answer keys: only the page, time, browser and the
// reference the service gave for this error.
export function HelpLink({ slug, children }: { slug: string; children: React.ReactNode }) {
  return (
    <Link href={`/help/articles/${slug}`} className="text-accent underline">
      {children}
    </Link>
  );
}

export function CopyDiagnostics({ reference }: { reference?: string | null }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    const lines = [
      `Page: ${window.location.pathname}`,
      `Time: ${new Date().toISOString()}`,
      `Browser: ${navigator.userAgent}`,
      reference ? `Reference: ${reference}` : null,
    ].filter(Boolean);
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <button type="button" onClick={() => void copy()} className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium">
      {copied ? "Copied" : "Copy details for support"}
    </button>
  );
}
