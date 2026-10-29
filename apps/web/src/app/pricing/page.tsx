import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { CommerceTermsState, Product } from "@portal/contracts";
import { GlassCard } from "@/components/glass-card";
import { CardTitle, IconTile, PageIcon } from "@/components/learner-pages";
import { PageHero } from "@/components/page-hero";
import { Notice, SkeletonLines } from "@/components/ui";
import { formatMinor } from "@/lib/money";
import { api } from "@/lib/session";
import { TIME_ZONE } from "@/lib/dates";

// P14.S1.T3 (PRICING-01): what is on sale, at what full price, for how long and covering what, with the purchase terms
// the owner published (tax, renewal, buying during the trial, refunds). Read from the API at request time. There is no
// checkout: payments aren't connected (BLOCKERS B06), so nothing here can be bought yet, and the page says so.
export const metadata: Metadata = {
  title: "Plans and prices",
  description: "Plans for Class 11 and 12, their full prices, what each covers, and the purchase terms.",
};

type Scope = { grades?: number[]; subjects?: string[]; exams?: string[] };
const KIND: Record<string, string> = { platform: "Everything", subject_package: "Subject plan", exam_package: "Exam plan", bundle: "Bundle" };
const subjectName = (code: string) => code.charAt(0).toUpperCase() + code.slice(1).replaceAll("_", " ");

function covers(p: Product): string {
  const s = p.scope as Scope;
  if (p.kind === "platform") return "Every subject published for Class 11 and Class 12, and every exam pattern";
  const parts = (s.grades ?? []).flatMap((g) => (s.subjects ?? []).map((sub) => `Class ${g === 11 ? "11" : "12"} ${subjectName(sub)}`));
  return [...parts, ...(s.exams ?? []).map((x) => `${x} mock tests`)].join(", ");
}

export default function PricingPage() {
  return (
    <div className="space-y-8">
      <PageHero
        eyebrow="Class 11 · Class 12"
        title="Plans and prices"
        lead="Every new account can start one free 30-day trial of everything published, without payment details. Prices below are the full price for the whole period shown."
      />
      <Suspense fallback={<SkeletonLines lines={6} label="Loading plans" />}>
        <Plans />
      </Suspense>
    </div>
  );
}

async function Plans() {
  const [products, terms] = await Promise.all([api<Product[]>("/v1/products"), api<CommerceTermsState>("/v1/commerce-terms")]);
  if (!products.ok || !terms.ok) {
    return <Notice tone="warn" title="Couldn't load plans">Please try again in a moment.</Notice>;
  }
  const priced = products.data.filter((p) => p.price !== null);
  const published = terms.data.published;
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <Notice title="Buying isn't available yet">
        Payments aren&apos;t connected, so no plan can be bought here yet. You can{" "}
        <Link href="/signin" className="text-accent underline underline-offset-2">
          create an account and start the free trial
        </Link>{" "}
        now.
      </Notice>
      {priced.length === 0 ? (
        <GlassCard className="text-center text-muted">No plans are on sale yet. They&apos;ll appear here with their full price when they are.</GlassCard>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2" aria-label="Plans on sale">
          {priced.map((p) => (
            <GlassCard as="li" key={p.code} className="flex flex-col gap-4">
              <div className="flex items-start gap-3">
                <IconTile icon={p.kind === "platform" ? "graduation-cap" : "credit-card"} />
                <div className="min-w-0">
                  <p className="text-xs font-semibold tracking-[0.15em] text-accent uppercase">{KIND[p.kind] ?? p.kind}</p>
                  <h2 className="font-display text-xl font-semibold tracking-tight break-words">{p.name}</h2>
                </div>
              </div>
              <p className="font-display text-[34px] leading-10 font-bold tracking-tight">{formatMinor(p.price!.amount_minor ?? 0, p.price!.currency)}</p>
              <dl className="space-y-2 border-t border-border pt-4 text-sm">
                {(
                  [
                    ["Valid for: ", `${p.duration_days} days (see the purchase terms below)`],
                    ["Covers: ", covers(p)],
                  ] as const
                ).map(([term, value]) => (
                  <div key={term}>
                    <dt className="inline font-medium">
                      <PageIcon name="check" size={16} className="mr-1.5 inline-block align-[-3px] text-accent" />
                      {term}
                    </dt>
                    <dd className="inline">{value}</dd>
                  </div>
                ))}
                <div>
                  <dt className="inline font-medium">
                    <PageIcon name="check" size={16} className="mr-1.5 inline-block align-[-3px] text-accent" />
                    Written answers marked by teachers:{" "}
                  </dt>
                  <dd className="inline">
                    {p.written_units} units included
                    {/* PILOT-R0-01: said before anything is bought, never after */}
                    {p.written_pilot_only && " (usable once written practice opens beyond the current teacher-reviewed pilot)"}
                  </dd>
                </div>
              </dl>
              {p.description && <p className="text-sm text-muted">{p.description}</p>}
            </GlassCard>
          ))}
        </ul>
      )}
      {/* The terms are reading text: a glass card with the text itself on the solid surface. */}
      <GlassCard as="section" aria-labelledby="terms-heading" className="space-y-4">
        <CardTitle id="terms-heading" icon="file-text">
          Purchase terms
        </CardTitle>
        {published === null ? (
          <p className="text-muted">The purchase terms haven&apos;t been published yet. They will be here, in full, before anything can be bought.</p>
        ) : (
          <div className="space-y-3 rounded-inner border border-border bg-surface p-5 text-sm sm:p-6">
            <dl className="space-y-3">
              {(
                [
                  ["Taxes", published.tax_note],
                  ["Renewal", published.renewal_note],
                  ["Buying during your free trial", published.conversion_note],
                  ["Refunds", published.refund_note],
                ] as const
              ).map(([label, text]) => (
                <div key={label}>
                  <dt className="font-medium">{label}</dt>
                  <dd className="max-w-3xl whitespace-pre-line text-muted">{text}</dd>
                </div>
              ))}
            </dl>
            <p className="text-xs text-muted">
              Version {published.version}
              {published.published_at ? `, published ${new Date(published.published_at).toLocaleDateString("en-GB", { dateStyle: "long", timeZone: TIME_ZONE })}` : ""}.
            </p>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
