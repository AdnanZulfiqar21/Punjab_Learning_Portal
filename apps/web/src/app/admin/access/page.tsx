import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { AccessGrant } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { TIME_ZONE } from "@/lib/dates";
import { api, currentUser } from "@/lib/session";
import { GrantForm, RevokeGrant } from "./controls";

export const metadata: Metadata = { title: "Access grants", robots: { index: false } };

const SOURCE: Record<string, string> = { scholarship: "Scholarship", promotional: "Promotional", pilot: "Pilot" };
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE });

// P04.S2.T3 (ACCESS-GRANTS-01): staff grants of scholarship, promotional and pilot access. During the R0 written pilot
// (PILOT-R0-01), a pilot grant is what lets a learner start written practice; its units fund those tests.
export default function AccessGrantsPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Access grants" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Access grants</h1>
        <p className="text-muted">
          Scholarship, promotional and pilot access given by staff. Each grant is recorded with your reason; a revoked grant stays on record. Paid
          plans aren&apos;t sold yet.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Loading access grants" />}>
        <Grants />
      </Suspense>
    </div>
  );
}

async function Grants() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/access");
  const res = await api<AccessGrant[]>("/v1/admin/entitlements", { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Not available to you" : "Couldn't load access grants"}>
        {res.status === 403 ? "Finance and the owner can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
      </Notice>
    );
  }
  return (
    <div className="space-y-6">
      <section aria-labelledby="grant-h" className="space-y-3">
        <h2 id="grant-h" className="text-lg font-semibold">
          Grant access
        </h2>
        <p className="text-sm text-muted">The learner needs an account first. Written units are the written-marking allowance for the period.</p>
        <GrantForm />
      </section>
      <section aria-labelledby="current-h" className="space-y-3">
        <h2 id="current-h" className="text-lg font-semibold">
          Active grants ({res.data.length})
        </h2>
        {res.data.length === 0 ? (
          <p className="text-muted">No staff grant is active.</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Active access grants">
            {res.data.map((g) => (
              <li key={g.id} className="space-y-2 px-4 py-3 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium">
                    {g.email} · {SOURCE[g.source] ?? g.source}
                  </p>
                  <p className="text-muted">
                    {day(g.starts_at)} to {day(g.ends_at)}
                  </p>
                </div>
                <p>
                  Written units: {g.units_consumed} used, {g.units_held} held for unmarked tests, of {g.written_units}
                  {g.product_code !== "platform" ? ` · product ${g.product_code}` : ""}
                </p>
                <p className="text-muted">Reason: {g.reason}</p>
                <RevokeGrant id={g.id} label={`${g.email} (${SOURCE[g.source] ?? g.source})`} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
