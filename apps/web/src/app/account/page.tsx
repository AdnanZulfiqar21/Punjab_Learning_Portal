import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { revokeOtherSessions, revokeSession } from "@/app/actions/auth";
import { SignOutForm } from "@/components/sign-out-form";
import { ButtonLink, buttonClasses } from "@/components/button";
import { GlassCard } from "@/components/glass-card";
import { CardTitle, PageIcon } from "@/components/learner-pages";
import { PageHero } from "@/components/page-hero";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { currentUser, listSessions } from "@/lib/session";
import { STUDIO_ROLES } from "@/lib/studio";
import { getAccess } from "@/lib/access";
import { PlanStatus } from "@/components/plan-status";
import { RemoveTrialDevice } from "@/components/trial-devices";
import { NotificationPreferences } from "@/components/notification-preferences";
import type { AssistedAccess, NotificationPreferences as Prefs, StudySettings, TrialDevice } from "@portal/contracts";
import { AssistedAccessList } from "@/components/assisted-access";
import { DeleteAccount } from "@/components/delete-account";
import { api } from "@/lib/session";
import { DISPLAY_COOKIE, parseDisplay } from "@/lib/display";
import { StudySettingsForm } from "@/components/study-settings";
import { TIME_ZONE } from "@/lib/dates";

export const metadata: Metadata = { title: "Your account", robots: { index: false } };

export default function AccountPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Account" }]} />
      <PageHero
        eyebrow="Account"
        title="Your account"
        lead="Your profile, plan, notifications, display settings, data and signed-in devices."
        className="pt-2! pb-2! sm:pt-6!"
      />
      <Suspense fallback={<SkeletonLines lines={6} label="Loading your account" />}>
        <Account />
      </Suspense>
    </div>
  );
}

const fmt = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });
const SURFACE_NAME: Record<string, string> = { android: "Android app", ios: "iPhone or iPad app", web: "Web browser" };
const METHOD_NOTE: Record<string, string> = {
  exception: "allowed after a support review",
  fallback: "added while device checks were unavailable",
};

// DESIGN-01: each section is a glass card; the scroll margin keeps a section's heading clear of the floating header
// when it is opened from the section links. Lists of devices sit on the solid surface inside their card.
const CARD = "scroll-mt-28";
const LIST = "divide-y divide-border rounded-inner border border-border bg-surface";

// The staff pages each role may open, in the order they were listed before (studio/ and admin/ check roles again).
const isOwnerOrFinance = (r: string[]) => r.some((x) => x === "owner_admin" || x === "finance");
const STAFF_LINKS: { href: string; label: string; show: (roles: string[]) => boolean }[] = [
  { href: "/studio", label: "Content studio", show: (r) => r.some((x) => STUDIO_ROLES.has(x)) },
  { href: "/admin/audit", label: "Audit trail", show: (r) => r.includes("owner_admin") },
  { href: "/admin/catalogue", label: "Catalogue", show: (r) => r.includes("owner_admin") },
  { href: "/admin/business", label: "Business overview", show: isOwnerOrFinance },
  { href: "/admin/products", label: "Products and prices", show: (r) => r.includes("finance") },
  { href: "/admin/funnel", label: "Learning funnel", show: isOwnerOrFinance },
  { href: "/admin/learning", label: "Learning and engagement", show: isOwnerOrFinance },
  { href: "/admin/economics", label: "Cohort economics", show: isOwnerOrFinance },
  { href: "/admin/trial-decisions", label: "Trial decisions", show: isOwnerOrFinance },
  { href: "/admin/access", label: "Access grants", show: isOwnerOrFinance },
  { href: "/admin/staff", label: "Staff", show: (r) => r.includes("owner_admin") },
  { href: "/admin/service", label: "Service overview", show: (r) => r.includes("platform_operator") },
  { href: "/admin/exam-profiles", label: "Exam profiles", show: (r) => r.some((x) => x === "owner_admin" || x === "academic_adjudicator") },
  { href: "/studio/support", label: "Support queue", show: (r) => r.some((x) => ["support", "subject_reviewer", "academic_adjudicator"].includes(x)) },
];

async function Account() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/account");
  const { me, token } = user;
  const [sessions, access, prefs, assists, trialDevices, settings, jar] = await Promise.all([
    listSessions(token),
    getAccess(token),
    api<Prefs>("/v1/me/notification-preferences", { token }),
    api<AssistedAccess[]>("/v1/me/assisted-access", { token }),
    api<TrialDevice[]>("/v1/me/trial/devices", { token }),
    api<StudySettings>("/v1/me/settings", { token }),
    cookies(),
  ]);
  const p = me.profile;
  const staffLinks = STAFF_LINKS.filter((l) => l.show(me.roles));
  // Links to the sections this account actually shows.
  const jump: [string, string][] = [["profile", "Profile"]];
  if (access) jump.push(["plan", "Plan"]);
  if (prefs.ok) jump.push(["notifications", "Notifications"]);
  if (settings.ok) jump.push(["display", "Display"]);
  jump.push(["your-data", "Your data"], ["devices", "Devices"]);
  return (
    <div className="space-y-6">
      <nav aria-label="Account sections" className="-mx-1 overflow-x-auto px-1 pb-1">
        <ul className="mx-auto flex w-max gap-2">
          {jump.map(([id, label]) => (
            <li key={id}>
              <a
                href={`#${id}`}
                className="glass inline-flex min-h-11 items-center rounded-full px-4 text-sm font-medium shadow-none transition duration-200 hover:border-accent hover:text-accent"
              >
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <GlassCard as="section" id="profile" aria-labelledby="profile-heading" className={`${CARD} space-y-4`}>
        <CardTitle id="profile-heading" icon="user" action={me.roles.length > 0 ? <Badge>{me.roles.join(", ")}</Badge> : undefined}>
          {me.email}
        </CardTitle>
        {p ? (
          <dl className="grid gap-x-6 gap-y-2 rounded-inner border border-border bg-surface p-4 text-sm sm:grid-cols-[max-content_1fr]">
            <dt className="text-muted">Class</dt>
            <dd className="font-medium">{p.grade ? GRADE_LABEL[p.grade] : "Not set"}</dd>
            <dt className="text-muted">Subjects</dt>
            <dd className="font-medium">{p.subjects?.length ? p.subjects.map((s) => s.replace("_", " ")).join(", ") : "Not set"}</dd>
            <dt className="text-muted">Entry tests</dt>
            <dd className="font-medium">{p.target_exams?.length ? p.target_exams.map((e) => e.toUpperCase()).join(", ") : "None"}</dd>
            <dt className="text-muted">Daily study time</dt>
            <dd className="font-medium">{p.daily_minutes ? `${p.daily_minutes} minutes` : "Not set"}</dd>
          </dl>
        ) : (
          <Notice title="Finish setting up">Tell us your class and subjects so we can show the right books.</Notice>
        )}
        <ButtonLink href="/onboarding" variant="secondary">
          <PageIcon name="sliders-horizontal" size={16} />
          {p ? "Edit learning preferences" : "Set up learning preferences"}
        </ButtonLink>
        {staffLinks.length > 0 && (
          <nav aria-label="Staff tools" className="space-y-2 border-t border-border pt-4">
            <p className="text-xs font-semibold tracking-[0.15em] text-muted uppercase">Staff tools</p>
            <ul className="flex flex-wrap gap-2">
              {staffLinks.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    className="inline-flex min-h-11 items-center rounded-full border border-border bg-surface px-4 text-sm font-medium text-accent transition duration-200 hover:border-accent"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </GlassCard>

      {access && (
        <GlassCard as="section" id="plan" aria-labelledby="plan-heading" className={`${CARD} space-y-4`}>
          <CardTitle id="plan-heading" icon="credit-card">
            Your plan
          </CardTitle>
          <PlanStatus access={access} />
        </GlassCard>
      )}

      {trialDevices.ok && trialDevices.data.length > 0 && (
        <GlassCard as="section" aria-labelledby="trial-devices-heading" className={`${CARD} space-y-4`}>
          <CardTitle id="trial-devices-heading" icon="smartphone">
            Devices on your free trial
          </CardTitle>
          <p className="text-sm text-muted">
            Up to 3 devices can use your free trial. Removing one frees a place for another. A removed phone or tablet can&apos;t rejoin the trial by itself; if
            you removed one by mistake, ask for help.
          </p>
          <ul className={LIST}>
            {trialDevices.data.map((d) => {
              const name = d.label || SURFACE_NAME[d.surface] || "Device";
              return (
                <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
                  <span>
                    <span className="font-medium">{name}</span>
                    <span className="block text-muted">
                      {SURFACE_NAME[d.surface] ?? d.surface} · added {fmt(d.authorized_at)}
                      {METHOD_NOTE[d.method] ? ` · ${METHOD_NOTE[d.method]}` : ""}
                    </span>
                  </span>
                  <RemoveTrialDevice id={d.id} label={name} />
                </li>
              );
            })}
          </ul>
        </GlassCard>
      )}

      {prefs.ok && (
        <GlassCard as="section" id="notifications" aria-labelledby="notifications-heading" className={`${CARD} space-y-4`}>
          <CardTitle
            id="notifications-heading"
            icon="bell"
            action={
              <Link href="/notifications" className="inline-flex min-h-11 items-center font-medium text-accent underline-offset-2 hover:underline">
                Open your notifications
              </Link>
            }
          >
            Notifications
          </CardTitle>
          <NotificationPreferences initial={prefs.data} />
        </GlassCard>
      )}

      {settings.ok && (
        <GlassCard as="section" id="display" aria-labelledby="settings-heading" className={`${CARD} space-y-4`}>
          <CardTitle id="settings-heading" icon="monitor">
            Display and data
          </CardTitle>
          <StudySettingsForm initial={settings.data} current={parseDisplay(jar.get(DISPLAY_COOKIE)?.value)} />
        </GlassCard>
      )}

      {assists.ok && assists.data.length > 0 && (
        <GlassCard as="section" aria-labelledby="assist-heading" className={`${CARD} space-y-4`}>
          <CardTitle id="assist-heading" icon="eye">
            Support access to your activity
          </CardTitle>
          <p className="text-sm text-muted">Times a support team member could see a summary of your activity to help with a request. They can never act as you.</p>
          <AssistedAccessList items={assists.data} now={new Date().toISOString()} />
        </GlassCard>
      )}

      <GlassCard as="section" id="your-data" aria-labelledby="privacy-heading" className={`${CARD} space-y-4`}>
        <CardTitle id="privacy-heading" icon="shield">
          Your data
        </CardTitle>
        <p className="text-sm text-muted">Download a copy of the personal data we hold about you, or ask us to delete your account.</p>
        <div className="flex flex-wrap gap-3">
          <a href="/account/data-export" className={buttonClasses({ variant: "secondary" })}>
            <PageIcon name="download" size={16} />
            Download my data
          </a>
          <ButtonLink href="/account/exports" variant="secondary">
            <PageIcon name="file-text" size={16} />
            Exports
          </ButtonLink>
        </div>
        <DeleteAccount />
      </GlassCard>

      <GlassCard as="section" id="devices" aria-labelledby="sessions-heading" className={`${CARD} space-y-4`}>
        <CardTitle
          id="sessions-heading"
          icon="lock"
          action={
            sessions.length > 1 && (
              <form action={revokeOtherSessions}>
                <button type="submit" className="inline-flex min-h-11 items-center font-medium text-accent underline-offset-2 hover:underline">
                  Sign out everywhere else
                </button>
              </form>
            )
          }
        >
          Signed-in devices
        </CardTitle>
        <ul className={LIST}>
          {sessions.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
              <span className="flex items-start gap-3">
                <PageIcon name={s.kind === "web" ? "monitor" : "smartphone"} size={18} className="mt-0.5 shrink-0 text-muted" />
                <span>
                  <span className="mr-2 font-medium">{s.device_label ?? (s.kind === "web" ? "Web browser" : "Mobile app")}</span>
                  {s.current && <Badge tone="ok">This device</Badge>}
                  <span className="block text-muted">
                    Last active {fmt(s.last_seen_at)} · signed in {fmt(s.created_at)}
                  </span>
                </span>
              </span>
              {!s.current && (
                <form action={revokeSession}>
                  <input type="hidden" name="session_id" value={s.id} />
                  <button type="submit" className={buttonClasses({ variant: "secondary", className: "hover:border-danger! hover:text-danger!" })}>
                    Sign out
                  </button>
                </form>
              )}
            </li>
          ))}
        </ul>
      </GlassCard>

      <GlassCard as="section" aria-labelledby="signout-heading" className={`${CARD} space-y-4`}>
        <CardTitle id="signout-heading" icon="log-out">
          Sign out
        </CardTitle>
        <SignOutForm />
      </GlassCard>
    </div>
  );
}
