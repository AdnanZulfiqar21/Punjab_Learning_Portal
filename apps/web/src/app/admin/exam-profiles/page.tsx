import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { ExamProfileAdmin, MockSession } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { DraftEditor, NewProfile, RULES_TEMPLATE, VerifyPublish } from "./controls";
import { Accommodation, ScheduleSession } from "./sessions";

export const metadata: Metadata = { title: "Exam profiles", robots: { index: false } };

export default function ExamProfilesPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Exam profiles" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Exam profiles</h1>
        <p className="text-muted">
          Official test patterns as versioned data. Two different people (never the author) verify each version against its source before it can be published. Publishing a new version
          only affects new mocks.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading profiles" />}>
        <Profiles />
      </Suspense>
    </div>
  );
}

async function Profiles() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/exam-profiles");
  if (!user.me.roles.some((r) => r === "owner_admin" || r === "academic_adjudicator")) {
    return <Notice tone="warn" title="Not available">Only the owner, admins and academic adjudicators manage exam profiles.</Notice>;
  }
  const res = await api<ExamProfileAdmin[]>("/v1/admin/exam-profiles", { token: user.token });
  const sessions = await api<MockSession[]>("/v1/mock-sessions", { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Multi-factor sign-in needed" : "Couldn't load profiles"}>
        {res.problem?.detail ?? "Please try again."}
      </Notice>
    );
  }
  return (
    <div className="space-y-6">
      <NewProfile />
      {res.data.length === 0 && <Notice title="No profiles yet">Create one, then enter its first version from the official source.</Notice>}
      {res.data.map((p) => {
        const draft = p.versions.find((v) => v.status === "draft");
        return (
          <section key={p.id} aria-labelledby={`p-${p.id}`} className="space-y-3 rounded-xl border border-border bg-surface p-4">
            <h2 id={`p-${p.id}`} className="font-semibold">
              {p.code} · {p.name}
            </h2>
            {p.eligibility_note && <p className="text-sm text-muted">{p.eligibility_note}</p>}
            <ul className="space-y-3" aria-label={`${p.code} versions`}>
              {p.versions.map((v) => (
                <li key={v.id} className="space-y-2 rounded-lg border border-border p-3 text-sm">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">
                      Version {v.version} · {v.year}
                    </span>
                    <Badge tone={v.status === "published" ? "ok" : v.status === "retired" ? "info" : "warn"}>{v.status}</Badge>
                    <span className="text-muted">
                      {v.total_questions} questions · {String(v.rules.duration_minutes)} minutes · {v.verifications}/2 verifications
                    </span>
                  </p>
                  <VerifyPublish versionId={v.id} status={v.status} />
                </li>
              ))}
            </ul>
            {p.versions.some((v) => v.status === "published") && (
              <details className="text-sm">
                <summary className="cursor-pointer font-medium">Schedule a mock window</summary>
                <div className="pt-2">
                  <ScheduleSession code={p.code} />
                </div>
              </details>
            )}
            {sessions.ok &&
              sessions.data
                .filter((s) => s.profile_code === p.code)
                .map((s) => (
                  <div key={s.id} className="space-y-1 rounded-lg border border-border p-3 text-sm">
                    <p className="font-medium">
                      {s.title} · {s.state.replace("_", " ")}
                    </p>
                    <Accommodation sessionId={s.id} />
                  </div>
                ))}
            <details className="text-sm">
              <summary className="cursor-pointer font-medium">{draft ? `Edit draft version ${draft.version}` : "Start a new version"}</summary>
              <div className="pt-2">
                <DraftEditor
                  profileId={p.id}
                  versionId={draft?.id ?? null}
                  initialYear={draft?.year ?? new Date().getFullYear()}
                  initialRules={draft ? JSON.stringify(draft.rules, null, 2) : RULES_TEMPLATE}
                />
              </div>
            </details>
          </section>
        );
      })}
    </div>
  );
}
