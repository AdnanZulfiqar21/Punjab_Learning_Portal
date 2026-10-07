// Server-only helpers for the staff content studio (P06). Every request carries the signed-in person's session; the
// API decides what they may see and do. Drafts are private staff data and are never cached.
import { redirect } from "next/navigation";
import type { Me, StudioHistoryEvent, StudioItem, StudioItemSummary } from "@portal/contracts";
import { api, currentUser } from "@/lib/session";

export const STUDIO_ROLES = new Set(["content_author", "subject_reviewer", "academic_adjudicator", "publisher"]);

export class StudioForbiddenError extends Error {
  constructor() {
    super("The content studio is for staff with a content role.");
    this.name = "StudioForbiddenError";
  }
}

/** The signed-in staff member, or a redirect to sign-in. Throws StudioForbiddenError for non-staff. */
export async function requireStaff(next: string): Promise<{ me: Me; token: string }> {
  const user = await currentUser();
  if (!user) redirect(`/signin?next=${encodeURIComponent(next)}`);
  if (!user.me.roles.some((r) => STUDIO_ROLES.has(r))) throw new StudioForbiddenError();
  return user;
}

export type QueueFilters = { state?: string; availability?: string; grade?: string; subject?: string; mine?: string };

export async function getQueue(token: string, filters: QueueFilters): Promise<StudioItemSummary[]> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v);
  const res = await api<StudioItemSummary[]>(`/v1/studio/queue?${params.toString()}`, { token });
  if (!res.ok) throw new Error(res.problem?.detail ?? `Could not load the queue (${res.status}).`);
  return res.data;
}

export async function getItem(token: string, id: string): Promise<StudioItem | null> {
  const res = await api<StudioItem>(`/v1/studio/items/${encodeURIComponent(id)}`, { token });
  if (res.ok) return res.data;
  if (res.status === 404 || res.status === 422) return null;
  throw new Error(res.problem?.detail ?? `Could not load the item (${res.status}).`);
}

export async function getHistory(token: string, id: string): Promise<StudioHistoryEvent[]> {
  const res = await api<StudioHistoryEvent[]>(`/v1/studio/items/${encodeURIComponent(id)}/history`, { token });
  return res.ok ? res.data : [];
}

export const STATE_LABEL: Record<string, string> = {
  draft: "Draft",
  submitted: "In review",
  changes_requested: "Changes requested",
  approved: "Approved",
  published: "Published",
};

export const AVAILABILITY_LABEL: Record<string, string> = {
  unpublished: "Not published",
  live: "Live",
  quarantined: "Quarantined",
  retired: "Retired",
};

export const SUBJECT_LABEL: Record<string, string> = {
  biology: "Biology",
  chemistry: "Chemistry",
  physics: "Physics",
  computer_science: "Computer Science",
  mathematics: "Mathematics",
};
