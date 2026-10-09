"use client";

export function PrintButton() {
  return (
    <button type="button" onClick={() => window.print()} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent print:hidden">
      Print or save as PDF
    </button>
  );
}
