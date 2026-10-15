// W04.S3.T3 (MOBILE-LINKED-01): a new practice test linked to a marked written test. It is marked on its own, uses the
// written allowance when it starts, and never changes the earlier result (a recheck is the route for that).
import type { LinkedForm, WrittenResult } from "@portal/contracts";

export type LinkedAttempt = NonNullable<WrittenResult["linked_attempts"]>[number];

export const LINKED_REASON: Record<string, string> = {
  REWRITE: "You asked to answer these questions again after seeing your feedback.",
  NEW_CONTENT: "A teacher found new or changed work in the copy you sent, so it can only be marked as a new test.",
  INDETERMINATE: "A teacher couldn't tell whether your copy showed the same work, so you can answer again as a new test.",
};

export const LINKED_STATUS: Record<string, string> = {
  not_started: "not started",
  active: "in progress",
  sealed: "submitted",
  expired: "expired",
};

/** Where a linked test opens: the test itself once started, otherwise its confirmation screen. */
export function linkedRoute(l: Pick<LinkedAttempt, "attempt_id" | "form_id">):
  | { pathname: "/written/[id]"; params: { id: string } }
  | { pathname: "/written/linked/[formId]"; params: { formId: string } } {
  return l.attempt_id ? { pathname: "/written/[id]", params: { id: l.attempt_id } } : { pathname: "/written/linked/[formId]", params: { formId: l.form_id } };
}

/** Whether the allowance covers starting it; the server decides again when it starts. */
export function canStart(f: Pick<LinkedForm, "allowance_available" | "allowance_units">): boolean {
  return f.allowance_available >= f.allowance_units;
}

/** Questions picked to practise again, kept in order; the last one can't be unpicked by accident into an empty set. */
export function togglePosition(picked: readonly number[], position: number): number[] {
  if (picked.includes(position)) return picked.filter((p) => p !== position);
  return [...picked, position].sort((a, b) => a - b);
}
