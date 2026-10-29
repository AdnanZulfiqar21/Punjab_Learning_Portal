// The learner's plan on mobile: same server decision as web. Only the free trial and staff-granted access exist today;
// paid plans need a payment provider/store billing that isn't connected yet (BLOCKERS B06/B07).
import { useState } from "react";
import { View } from "react-native";
import type { Access, TrialDecision } from "@portal/contracts";

import { Button } from "@/components/form";
import { Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";
import { TIME_ZONE } from "@/lib/dates";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "long", timeZone: TIME_ZONE });

// P14.S1.T2: what the current plans cover; null when one covers everything (the platform or the free trial).
function coverage(entitlements: Access["entitlements"]): string | null {
  const parts: string[] = [];
  for (const e of entitlements) {
    const s = (e.scope ?? {}) as { grades?: number[]; subjects?: string[]; exams?: string[] };
    if (!s.grades?.length && !s.subjects?.length && !s.exams?.length) return null;
    const name = (code: string) => code.charAt(0).toUpperCase() + code.slice(1).replaceAll("_", " ");
    for (const g of s.grades ?? []) for (const sub of s.subjects ?? []) parts.push(`Class ${g === 11 ? "11" : "12"} ${name(sub)}`);
    for (const x of s.exams ?? []) parts.push(`${x} mocks`);
  }
  return [...new Set(parts)].join(", ") || null;
}
const SOURCE: Record<string, string> = { trial: "Free trial", paid: "Paid plan", scholarship: "Scholarship access", promotional: "Promotional access", pilot: "Pilot access" };

// Trial decisions the server can return (roadmap §16.5): only "granted"/"active"/"device_authorized" unlock trial use.
const OK = new Set(["granted", "active", "device_authorized", "paid_active"]);

export function PlanCard({ access, token, onChange, purpose }: { access: Access; token: string; onChange: (a: Access) => void; purpose?: string }) {
  const c = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const active = access.entitlements.filter((e) => e.status === "active" && new Date(e.ends_at) > new Date());

  async function decide(run: () => Promise<TrialDecision>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const d = await run();
      if (!OK.has(d.state)) setNotice(d.message); // device used, review, verification pending, device limit: say so
      onChange(await api.access(token));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That didn't work. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (access.has_access && active.length > 0 && access.device_state === "device_authorization_required") {
    return (
      <View style={{ gap: Space.sm }}>
        <Notice tone="warn" title="Add this device to your free trial">
          Your trial is active on your account. Each device needs to be added once before you use the trial on it (up to 3
          devices).
        </Notice>
        {notice ? <Notice tone="warn" title="Trial on this device">{notice}</Notice> : null}
        {error ? <T style={{ color: c.danger }}>{error}</T> : null}
        <Button label="Use my trial on this device" busy={busy} onPress={() => decide(() => api.authorizeDevice(token))} />
      </View>
    );
  }
  if (access.has_access && active.length > 0) {
    const current = active.reduce((a, b) => (new Date(a.ends_at) > new Date(b.ends_at) ? a : b));
    // PILOT-R0-01: during the R0 pilot only pilot access opens written practice, and only its units count.
    const outsidePilot = access.written_pilot_only && !active.some((e) => e.source === "pilot");
    return (
      <Notice title={`${SOURCE[current.source] ?? "Access"} until ${day(current.ends_at)}`}>
        {coverage(active) ? `Your plan covers ${coverage(active)}. ` : ""}
        {outsidePilot
          ? "Written practice is in a teacher-reviewed pilot for invited learners for now."
          : `Written marking allowance${access.written_pilot_only ? " (pilot)" : ""}: ${access.written_allowance.available} of ${access.written_allowance.granted} units left.`}
      </Notice>
    );
  }
  if (access.trial.status === "available") {
    return (
      <View style={{ gap: Space.sm }}>
        <Notice title={purpose ? `${purpose} needs a plan` : "Start your free trial"}>
          Your free 30-day trial covers practice tests{access.written_pilot_only ? "" : ", written practice"} and every subject in Class 11 and
          12. It starts now and ends exactly 30 days later. No payment details are needed.
          {access.written_pilot_only ? " Written practice is in a teacher-reviewed pilot for invited learners for now." : ""}
        </Notice>
        {/* P14.S8.T2 (TRIAL-CONTROLS-01): what the one-trial rule checks, said before anyone starts. */}
        <T variant="small">
          There is one free trial per person. This app may also check whether this phone has already had a free trial; for that we keep only
          a random reference for the app on this phone, never the phone&apos;s identity. Shared or second-hand phone? Ask for help and a
          person will review it.
        </T>
        {notice ? <Notice tone="warn" title="Free trial">{notice}</Notice> : null}
        {error ? <T style={{ color: c.danger }}>{error}</T> : null}
        <Button
          label="Start my free 30-day trial"
          busy={busy}
          onPress={async () => {
            await decide(() => api.claimTrial(token));
          }}
        />
      </View>
    );
  }
  return (
    <Notice tone="warn" title={access.trial.status === "ended" && access.trial.ends_at ? `Your free trial ended on ${day(access.trial.ends_at)}` : "No active plan"}>
      {access.trial.reason ?? "Paid plans aren't available to buy yet. Lessons and chapter outlines stay free to read."}
    </Notice>
  );
}
