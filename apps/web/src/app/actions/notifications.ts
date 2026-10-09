"use server";

// P15.S1: the learner's notification inbox and preferences through the BFF.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { NotificationPreferences, Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(next: string): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(next)}`);
  return t;
}

/** Opens a notification: marks it read, then goes where it points (an app path only). */
export async function openNotification(id: string, link: string | null): Promise<void> {
  const t = await token("/notifications");
  await api<null>(`/v1/me/notifications/${encodeURIComponent(id)}/read`, { method: "POST", token: t });
  revalidatePath("/notifications");
  redirect(link && link.startsWith("/") && !link.startsWith("//") ? link : "/notifications");
}

export async function readAllNotifications(): Promise<void> {
  const t = await token("/notifications");
  await api<null>("/v1/me/notifications/read-all", { method: "POST", token: t });
  revalidatePath("/notifications");
}

export type PreferencesState = { ok?: boolean; error?: string } | undefined;

export async function savePreferences(_prev: PreferencesState, form: FormData): Promise<PreferencesState> {
  const t = await token("/account");
  const body: NotificationPreferences = {
    email_enabled: form.get("email_enabled") === "on",
    push_enabled: form.get("push_enabled") === "on",
    reminders_enabled: form.get("reminders_enabled") === "on",
    promotional_opt_in: form.get("promotional_opt_in") === "on",
    timezone: String(form.get("timezone") ?? "Asia/Karachi"),
    quiet_start: String(form.get("quiet_start") ?? "22:00"),
    quiet_end: String(form.get("quiet_end") ?? "07:00"),
  };
  const res = await api<NotificationPreferences>("/v1/me/notification-preferences", { method: "PUT", token: t, body: JSON.stringify(body) });
  if (!res.ok) return { error: (res.problem as Problem | null)?.detail ?? "Couldn't save your notification settings." };
  return { ok: true };
}
