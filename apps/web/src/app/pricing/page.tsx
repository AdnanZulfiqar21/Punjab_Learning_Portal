import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { CommerceTermsState, Product } from "@portal/contracts";
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
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Plans and prices</h1>
        <p className="max-w-2xl text-muted">
          Every new account can start one free 30-day trial of everything published, without payment details. Prices below are the full price for the whole period shown.
        </p>
      </div>
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
    <div className="space-y-8">
      <Notice title="Buying isn't available yet">
        Payments aren&apos;t connected, so no plan can be bought here yet. You can{" "}
        <Link href="/signin" className="text-accent underline underline-offset-2">
          create an account and start the free trial
        </Link>{" "}
        now.
      </Notice>
      {priced.length === 0 ? (
        <p className="text-muted">No plans are on sale yet. They&apos;ll appear here with their full price when they are.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2" aria-label="Plans on sale">
          {priced.map((p) => (
            <li key={p.code} className="space-y-3 rounded-xl border border-border bg-surface p-5">
              <div>
                <p className="text-sm text-muted">{KIND[p.kind] ?? p.kind}</p>
                <h2 className="text-lg font-semibold">{p.name}</h2>
              </div>
              <p className="text-2xl font-semibold">{formatMinor(p.price!.amount_minor ?? 0, p.price!.currency)}</p>
              <dl className="space-y-1 text-sm">
                <div>
                  <dt className="inline font-medium">Valid for: </dt>
                  <dd className="inline">{p.duration_days} days (see the purchase terms below)</dd>
                </div>
                <div>
                  <dt className="inline font-medium">Covers: </dt>
                  <dd className="inline">{covers(p)}</dd>
                </div>
                <div>
                  <dt className="inline font-medium">Written answers marked by teachers: </dt>
                  <dd className="inline">
                    {p.written_units} units included
                    {/* PILOT-R0-01: said before anything is bought, never after */}
                    {p.written_pilot_only && " (usable once written practice opens beyond the current teacher-reviewed pilot)"}
                  </dd>
                </div>
              </dl>
              {p.description && <p className="text-sm text-muted">{p.description}</p>}
            </li>
          ))}
        </ul>
      )}
      <section aria-labelledby="terms-heading" className="space-y-3">
        <h2 id="terms-heading" className="text-lg font-semibold">
          Purchase terms
        </h2>
        {published === null ? (
          <p className="text-muted">The purchase terms haven&apos;t been published yet. They will be here, in full, before anything can be bought.</p>
        ) : (
          <div className="max-w-3xl space-y-3 text-sm">
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
                  <dd className="whitespace-pre-line text-muted">{text}</dd>
                </div>
              ))}
            </dl>
            <p className="text-xs text-muted">
              Version {published.version}
              {published.published_at ? `, published ${new Date(published.published_at).toLocaleDateString("en-GB", { dateStyle: "long", timeZone: TIME_ZONE })}` : ""}.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
