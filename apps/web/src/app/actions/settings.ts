"use server";

// P04.S3.T2 (SETTINGS-01): the learner's usual study settings on the account. Only the settings given change.
import { redirect } from "next/navigation";
import type { Problem, StudySettings, StudySettingsPatch } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type SettingsResult = { ok: true; settings: StudySettings } | { ok: false; error: string };

export async function saveUsualSettings(patch: StudySettingsPatch): Promise<SettingsResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/account");
  const res = await api<StudySettings>("/v1/me/settings", { method: "PATCH", token: t, body: JSON.stringify(patch) });
  if (res.ok) return { ok: true, settings: res.data };
  return { ok: false, error: (res.problem as Problem | null)?.detail ?? `Couldn't save your settings (${res.status}).` };
}
