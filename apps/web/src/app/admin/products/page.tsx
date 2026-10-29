import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { Catalogue, CommerceTermsState, ProductAdmin } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { formatMinor } from "@/lib/money";
import { api, currentUser } from "@/lib/session";
import { AddPrice, MoveProduct, NewProduct, TermsEditor } from "./controls";
import { TIME_ZONE } from "@/lib/dates";

export const metadata: Metadata = { title: "Products and prices", robots: { index: false } };

const KIND: Record<string, string> = {
  platform: "Whole platform",
  subject_package: "Subject package",
  exam_package: "Exam package",
  bundle: "Bundle",
};
const STATUS: Record<string, { label: string; tone: "ok" | "info" | "warn" }> = {
  draft: { label: "Draft", tone: "info" },
  active: { label: "On sale", tone: "ok" },
  retired: { label: "Retired", tone: "warn" },
};

const money = (minor: number | null, currency: string) => (minor === null ? "not on sale" : formatMinor(minor, currency));
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });

export default function ProductsPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Products and prices" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Products and prices</h1>
        <p className="text-muted">
          What learners can buy, kept apart from its price. A product is a draft until it goes on sale; then its contents are fixed, and changing them means retiring it and defining
          a new one. Prices are added as new versions and never edited. Nothing is sold here yet: payments aren&apos;t connected.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading products" />}>
        <Products />
      </Suspense>
    </div>
  );
}

async function Products() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/products");
  const [res, catalogue, terms] = await Promise.all([
    api<ProductAdmin[]>("/v1/admin/products", { token: user.token }),
    api<Catalogue>("/v1/catalogue"),
    api<CommerceTermsState>("/v1/admin/commerce-terms", { token: user.token }),
  ]);
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Finance staff only" : "Couldn't load products"}>
        {res.status === 403 ? "Finance staff can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
      </Notice>
    );
  }
  const subjects = new Map<string, string>();
  for (const g of catalogue.ok ? catalogue.data.grades : []) for (const s of g.subjects) subjects.set(s.subject.code, s.subject.name);
  return (
    <div className="space-y-6">
      {terms.ok && <TermsEditor key={`${terms.data.published?.version}:${terms.data.draft?.version}`} state={terms.data} />}
      <NewProduct subjects={[...subjects].map(([code, name]) => ({ code, name }))} />
      {res.data.length === 0 ? (
        <p className="text-muted">No products are defined yet.</p>
      ) : (
        <ul className="space-y-4">
          {res.data.map((p) => {
            const scope = p.scope as { grades?: number[]; subjects?: string[]; exams?: string[] };
            return (
              <li key={p.id} className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <h2 className="text-base font-semibold">{p.name}</h2>
                    <p className="font-mono text-xs text-muted">{p.code}</p>
                  </div>
                  <Badge tone={STATUS[p.status]?.tone ?? "info"}>{STATUS[p.status]?.label ?? p.status}</Badge>
                </div>
                <p>
                  {KIND[p.kind] ?? p.kind} ·{" "}
                  {p.kind === "platform"
                    ? "everything in the active scope"
                    : [
                        scope.grades?.length ? `Class ${scope.grades.map((g) => (g === 11 ? "11" : "12")).join(" and ")}` : "",
                        (scope.subjects ?? []).map((s) => subjects.get(s) ?? s).join(", "),
                        (scope.exams ?? []).join(", "),
                      ]
                        .filter(Boolean)
                        .join(" · ")}{" "}
                  · {p.duration_days} days · {p.written_units} written answers
                </p>
                <p>
                  <span className="font-medium">Price now:</span>{" "}
                  {p.current_price ? money(p.current_price.on_sale ? p.current_price.amount_minor : null, p.current_price.currency) : "not priced yet"}
                </p>
                {p.price_history.length > 0 && (
                  <details>
                    <summary className="cursor-pointer text-accent">Price history ({p.price_history.length})</summary>
                    <ul className="mt-2 space-y-1">
                      {p.price_history.map((h, i) => (
                        <li key={i}>
                          {when(h.starts_at)}: {money(h.on_sale ? h.amount_minor : null, h.currency)}
                          {h.reason ? <span className="text-muted"> · {h.reason}</span> : null}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {p.status !== "retired" && <AddPrice id={p.id} name={p.name} />}
                {p.status === "draft" && <MoveProduct id={p.id} to="activate" label="Put on sale" />}
                {p.status !== "retired" && <MoveProduct id={p.id} to="retire" label="Retire" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
