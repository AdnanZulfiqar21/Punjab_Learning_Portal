import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { ContentAsset } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";
import { NewAsset, UploadVersion } from "./asset-forms";
import { MediaPackForm } from "./media-pack";

export const metadata: Metadata = { title: "Assets", robots: { index: false } };

// P07.S2.T4 (ASSETS-01): the owned master archive. Masters are kept privately with checksums and provenance; learners
// only ever get derived delivery copies (re-encoded images, validated PDFs, captions). Diagram sources are never served.
export default function AssetsPage({ searchParams }: PageProps<"/studio/assets">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "Assets" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Assets</h1>
        <p className="text-muted">
          Diagrams, handouts, captions and diagram sources. Every upload is a new, unchangeable version with its source recorded. Use a
          version&apos;s ID in content (for example an image fallback).
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading assets" />}>
        {searchParams.then((sp) => (
          <Archive grade={sp.grade === "12" ? 12 : 11} subject={typeof sp.subject === "string" ? sp.subject : "biology"} />
        ))}
      </Suspense>
    </div>
  );
}

const size = (n: number) => (n >= 1024 * 1024 ? `${(n / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

async function Archive({ grade, subject }: { grade: number; subject: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/studio/assets");
  const res = await api<ContentAsset[]>(`/v1/studio/assets?grade=${grade}&subject=${encodeURIComponent(subject)}`, { token: user.token });
  if (!res.ok) return <Notice tone="warn" title="Couldn't load assets">{res.problem?.detail ?? "Please try again."}</Notice>;
  return (
    <div className="space-y-6">
      <nav aria-label="Class and subject" className="flex flex-wrap gap-2">
        {[11, 12].map((g) =>
          SUBJECTS.map(([code, name]) => (
            <Link
              key={`${g}-${code}`}
              href={`/studio/assets?grade=${g}&subject=${code}`}
              aria-current={g === grade && code === subject ? "page" : undefined}
              className={`rounded-full border px-3 py-1.5 text-sm ${g === grade && code === subject ? "border-accent bg-accent-soft font-medium text-accent" : "border-border bg-surface"}`}
            >
              {GRADE_LABEL[g]} {name}
            </Link>
          )),
        )}
      </nav>
      <NewAsset grade={grade} subject={subject} />
      <MediaPackForm />
      {res.data.length === 0 && <Notice title="No assets here yet">Create one above, then upload its first version.</Notice>}
      <ul className="space-y-4">
        {res.data.map((a) => (
          <li key={a.id} className="space-y-3 rounded-xl border border-border bg-surface p-4">
            <p className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{a.title}</span>
              <Badge>{a.kind.replace("_", " ")}</Badge>
              {a.external_id && <span className="font-mono text-xs text-muted">pack key {a.external_id}</span>}
            </p>
            {(a.versions ?? []).length > 0 && (
              <table className="w-full text-sm">
                <thead className="text-left text-muted">
                  <tr>
                    <th className="py-1 pr-3 font-normal">Version</th>
                    <th className="py-1 pr-3 font-normal">File</th>
                    <th className="py-1 pr-3 font-normal">Source</th>
                    <th className="py-1 font-normal">Copies</th>
                  </tr>
                </thead>
                <tbody>
                  {(a.versions ?? []).map((v) => (
                    <tr key={v.id} className="border-t border-border align-top">
                      <td className="py-2 pr-3">
                        {v.number}
                        {v.referenced && <span className="block text-xs text-muted">in use</span>}
                      </td>
                      <td className="py-2 pr-3">
                        {v.media_type} · {size(v.master_bytes)}
                        {v.width && v.height ? ` · ${v.width}×${v.height}` : ""}
                        {v.pages ? ` · ${v.pages} pages` : ""}
                        <span className="block font-mono text-xs text-muted" title="Version ID for use in content">
                          {v.id}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        {v.provenance.source}
                        {v.provenance.licence ? <span className="block text-xs text-muted">{v.provenance.licence}</span> : null}
                      </td>
                      <td className="space-x-3 py-2">
                        {v.delivery_state === "ready" ? (
                          <a href={`/studio/assets/file/${v.id}?copy=delivery`} className="text-accent underline underline-offset-2">
                            Delivery copy
                          </a>
                        ) : (
                          <span className="text-muted">{v.delivery_state === "none" ? "Not served" : "Delivery copy purged"}</span>
                        )}
                        <a href={`/studio/assets/file/${v.id}?copy=master`} className="text-accent underline underline-offset-2">
                          Master
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <UploadVersion assetId={a.id} />
          </li>
        ))}
      </ul>
    </div>
  );
}
