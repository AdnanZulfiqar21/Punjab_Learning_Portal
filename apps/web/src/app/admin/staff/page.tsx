import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { StaffGrant } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { TIME_ZONE } from "@/lib/dates";
import { api, currentUser } from "@/lib/session";
import { AddStaffForm, RemoveRole } from "./controls";
import { ROLE_LABEL } from "./roles";

export const metadata: Metadata = { title: "Staff", robots: { index: false } };

const scopeText = (scope: Record<string, unknown>) => {
  const grades = Array.isArray(scope.grades) ? scope.grades.map((g) => (g === 11 ? "11" : "12")).join(", ") : "";
  const subjects = Array.isArray(scope.subjects) ? scope.subjects.map((s) => String(s).replace("_", " ")).join(", ") : "";
  return grades || subjects ? `Class ${grades || "any"} · ${subjects || "any subject"}` : "Everything this role allows";
};

export default function StaffPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Staff" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Staff</h1>
        <p className="text-muted">Who can do what. Give each person only the role and classes and subjects they need. Every change is recorded with your reason.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Loading staff" />}>
        <Staff />
      </Suspense>
    </div>
  );
}

async function Staff() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/staff");
  const res = await api<StaffGrant[]>("/v1/admin/staff", { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Not available to you" : "Couldn't load staff"}>
        {res.status === 403 ? "The owner and administrators can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
      </Notice>
    );
  }
  return (
    <div className="space-y-6">
      <section aria-labelledby="add-h" className="space-y-3">
        <h2 id="add-h" className="text-lg font-semibold">
          Add a role
        </h2>
        <p className="text-sm text-muted">The person needs an account first. You can&apos;t change your own roles; another administrator does that.</p>
        <AddStaffForm />
      </section>
      <section aria-labelledby="current-h" className="space-y-3">
        <h2 id="current-h" className="text-lg font-semibold">
          Current roles ({res.data.length})
        </h2>
        {res.data.length === 0 ? (
          <p className="text-muted">No staff roles yet.</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm" aria-label="Current staff roles">
            {res.data.map((g) => {
              const label = `${ROLE_LABEL[g.role] ?? g.role} for ${g.email ?? "this account"}`;
              return (
                <li key={g.id} className="space-y-2 px-3 py-3">
                  <p>
                    <span className="font-medium">{g.email ?? "(no email)"}</span> · {ROLE_LABEL[g.role] ?? g.role}
                    <span className="block text-xs text-muted">
                      {scopeText(g.scope)} · since {new Date(g.granted_at).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE })} · {g.reason}
                    </span>
                  </p>
                  {g.user_id !== user.me.id && <RemoveRole grantId={g.id} label={label} />}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
