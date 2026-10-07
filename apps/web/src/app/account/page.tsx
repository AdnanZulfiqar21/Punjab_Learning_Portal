import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { revokeOtherSessions, revokeSession, signOut } from "@/app/actions/auth";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { currentUser, listSessions } from "@/lib/session";

export const metadata: Metadata = { title: "Your account", robots: { index: false } };

export default function AccountPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Account" }]} />
      <h1 className="text-2xl font-semibold tracking-tight">Your account</h1>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading your account" />}>
        <Account />
      </Suspense>
    </div>
  );
}

const fmt = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

async function Account() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/account");
  const { me, token } = user;
  const sessions = await listSessions(token);
  const p = me.profile;
  return (
    <div className="space-y-8">
      <section aria-labelledby="profile-heading" className="space-y-3 rounded-xl border border-border bg-surface p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 id="profile-heading" className="font-semibold">
            {me.email}
          </h2>
          {me.roles.length > 0 && <Badge>{me.roles.join(", ")}</Badge>}
        </div>
        {p ? (
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
            <dt className="text-muted">Class</dt>
            <dd>{p.grade ? GRADE_LABEL[p.grade] : "Not set"}</dd>
            <dt className="text-muted">Subjects</dt>
            <dd>{p.subjects?.length ? p.subjects.map((s) => s.replace("_", " ")).join(", ") : "Not set"}</dd>
            <dt className="text-muted">Entry tests</dt>
            <dd>{p.target_exams?.length ? p.target_exams.map((e) => e.toUpperCase()).join(", ") : "None"}</dd>
            <dt className="text-muted">Daily study time</dt>
            <dd>{p.daily_minutes ? `${p.daily_minutes} minutes` : "Not set"}</dd>
          </dl>
        ) : (
          <Notice title="Finish setting up">Tell us your class and subjects so we can show the right books.</Notice>
        )}
        <Link href="/onboarding" className="inline-block text-sm text-accent underline-offset-2 hover:underline">
          {p ? "Edit learning preferences" : "Set up learning preferences"}
        </Link>
      </section>

      <section aria-labelledby="sessions-heading" className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 id="sessions-heading" className="font-semibold">
            Signed-in devices
          </h2>
          {sessions.length > 1 && (
            <form action={revokeOtherSessions}>
              <button type="submit" className="text-sm text-accent underline-offset-2 hover:underline">
                Sign out everywhere else
              </button>
            </form>
          )}
        </div>
        <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
          {sessions.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
              <span>
                <span className="font-medium">{s.device_label ?? (s.kind === "web" ? "Web browser" : "Mobile app")}</span>
                {s.current && <Badge tone="ok">This device</Badge>}
                <span className="block text-muted">
                  Last active {fmt(s.last_seen_at)} · signed in {fmt(s.created_at)}
                </span>
              </span>
              {!s.current && (
                <form action={revokeSession}>
                  <input type="hidden" name="session_id" value={s.id} />
                  <button type="submit" className="rounded-lg border border-border px-3 py-1.5 hover:border-danger">
                    Sign out
                  </button>
                </form>
              )}
            </li>
          ))}
        </ul>
      </section>

      <form action={signOut}>
        <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-danger">
          Sign out of this device
        </button>
      </form>
    </div>
  );
}
