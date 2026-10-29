// The learner's plan, shown wherever access matters. Honest about what exists: only the free trial and staff-granted
// access are live; paid plans need a payment provider that isn't connected yet (BLOCKERS B06).
import type { Access } from "@portal/contracts";
import { Notice } from "@/components/ui";
import { day } from "@/lib/access";
import { coverage } from "@/lib/plan-coverage";
import { StartTrialButton } from "./start-trial-button";

const SOURCE: Record<string, string> = {
  trial: "Free trial",
  paid: "Paid plan",
  scholarship: "Scholarship access",
  promotional: "Promotional access",
  pilot: "Pilot access",
};

export function PlanStatus({ access, purpose }: { access: Access; purpose?: string }) {
  const active = access.entitlements.filter((e) => e.status === "active" && new Date(e.ends_at) > new Date());
  // PILOT-R0-01: during the R0 pilot only pilot access opens written practice, and only its units count.
  const pilotOnly = access.written_pilot_only;
  const inPilot = active.some((e) => e.source === "pilot");
  if (access.has_access && active.length > 0) {
    const current = active.reduce((a, b) => (new Date(a.ends_at) > new Date(b.ends_at) ? a : b));
    const covers = coverage(active);
    const opening = covers ? `Your plan covers ${covers}. ` : pilotOnly && !inPilot ? "Practice tests are open. " : "Practice tests and written practice are open. ";
    return (
      <Notice tone="ok" title={`${SOURCE[current.source] ?? "Access"} until ${day(current.ends_at)}`}>
        {opening}
        {pilotOnly && !inPilot ? (
          "Written practice is in a teacher-reviewed pilot for invited learners for now."
        ) : (
          <>
            Written marking allowance{pilotOnly ? " (pilot)" : ""}: {access.written_allowance.available} of {access.written_allowance.granted} units left (a
            short question uses {access.weights.short}, a long one {access.weights.long}).
          </>
        )}
      </Notice>
    );
  }
  if (access.trial.status === "available") {
    return (
      <Notice title={purpose ? `${purpose} needs a plan` : "Start your free trial"}>
        <span className="block">
          Your free 30-day trial covers practice tests{pilotOnly ? "" : ", written practice"} and every subject in Class 11 and 12. It starts
          when you press the button and ends exactly 30 days later. It doesn&apos;t ask for payment details.
          {pilotOnly && ` Written practice is in a teacher-reviewed pilot for invited learners for now.`}
        </span>
        {/* P14.S8.T2 (TRIAL-CONTROLS-01): what the one-trial rule checks, said before anyone starts. */}
        <span className="mt-2 block text-sm text-muted">
          There is one free trial per person. Our apps may also check whether a phone has already had a free trial; for that we keep only a
          random reference for the app on this phone, never the phone&apos;s identity. Shared or second-hand phone? Ask for help and a
          person will review it.
        </span>
        <span className="mt-2 block">
          <StartTrialButton />
        </span>
      </Notice>
    );
  }
  return (
    <Notice tone="warn" title={access.trial.status === "ended" ? `Your free trial ended on ${day(access.trial.ends_at!)}` : "No active plan"}>
      {access.trial.reason ?? "Paid plans aren't available to buy yet. Lessons and chapter outlines stay free to read."}
    </Notice>
  );
}
