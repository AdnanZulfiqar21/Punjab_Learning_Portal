import type { ServiceStatus } from "@portal/contracts";
import { api } from "@/lib/session";

// P15.S2.T3: known outages and recoveries, shown on every page above the content (never replacing it, so a
// submission receipt or result stays visible). A status page hosted apart from the app needs its own hosting (B03).
const LABEL: Record<string, string> = {
  investigating: "Investigating",
  identified: "Cause found",
  monitoring: "Fix applied, monitoring",
  resolved: "Resolved",
};

export async function IncidentBanner() {
  const res = await api<ServiceStatus>("/v1/status").catch(() => null);
  if (!res || !res.ok) return null;
  const open = res.data.incidents.filter((i) => i.status !== "resolved");
  if (open.length === 0) return null;
  return (
    <div role="status" aria-label="Service status" className="border-b border-warn bg-warn-soft px-4 py-2 text-sm">
      <div className="mx-auto max-w-5xl space-y-1">
        {open.map((i) => (
          <p key={i.id}>
            <span className="font-semibold">{LABEL[i.status] ?? i.status}:</span> {i.title}
            {i.updates[0] ? ` — ${i.updates[0].message}` : ""}
          </p>
        ))}
      </div>
    </div>
  );
}
