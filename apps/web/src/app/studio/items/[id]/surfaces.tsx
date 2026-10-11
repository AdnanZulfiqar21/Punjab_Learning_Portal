"use client";

// P06.S3.T1 (SURFACES-01): one preview, every delivery surface. Web and phone render the same blocks at their own
// widths; the oldest supported app shows reviewed fallbacks instead of blocks it can't render. The checklist comes
// from the API for the last saved version.
import { useEffect, useState, type ReactNode } from "react";
import { itemSurfaces, type SurfaceReport } from "@/app/actions/studio-read";
import { LessonBlocks } from "@/components/lesson-blocks";

const LANGUAGE = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" } as Record<string, string>;
type Surface = "web" | "phone" | "oldest";

export function Surfaces({ itemId, revision, children }: { itemId: string; revision: number; children: ReactNode }) {
  const [surface, setSurface] = useState<Surface>("web");
  const [report, setReport] = useState<SurfaceReport | null>(null);
  useEffect(() => {
    let live = true;
    void itemSurfaces(itemId).then((r) => live && setReport(r));
    return () => {
      live = false;
    };
  }, [itemId, revision]);

  return (
    <div className="space-y-4">
      <div role="radiogroup" aria-label="Preview surface" className="flex flex-wrap gap-2 text-sm">
        {(
          [
            ["web", "Web"],
            ["phone", "Phone width"],
            ["oldest", "Oldest supported app"],
          ] as const
        ).map(([value, label]) => (
          <label key={value} className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 ${surface === value ? "border-accent bg-accent-soft" : "border-border"}`}>
            <input type="radio" name="surface" value={value} checked={surface === value} onChange={() => setSurface(value)} /> {label}
          </label>
        ))}
      </div>
      {surface === "web" && children}
      {surface === "phone" && <div className="mx-auto max-w-[390px] rounded-2xl border border-border p-4">{children}</div>}
      {surface === "oldest" && (
        <div className="mx-auto max-w-[390px] space-y-4 rounded-2xl border border-border p-4">
          {!report ? (
            <p className="text-sm text-muted">Loading the oldest app&apos;s view…</p>
          ) : (
            report.oldest_client.map((g) => (
              <section key={g.where} className="space-y-2">
                <h3 className="text-sm font-medium text-muted">{g.where}</h3>
                {g.blocks.map((b, i) =>
                  b.type === "fallback" ? (
                    <div key={i} className="space-y-2 rounded-lg border border-dashed border-border px-3 py-2">
                      {b.image_asset_id ? (
                        // eslint-disable-next-line @next/next/no-img-element -- archived, scope-checked studio copy
                        <img src={`/studio/assets/file/${String(b.image_asset_id)}?copy=delivery`} alt={String(b.text || "Fallback image")} className="max-w-full rounded" />
                      ) : null}
                      <p>{String(b.text || "(no fallback yet)")}</p>
                    </div>
                  ) : (
                    <LessonBlocks key={i} blocks={[b]} headingOffset={2} assetUrl={(v) => `/studio/assets/file/${v}?copy=delivery`} />
                  ),
                )}
              </section>
            ))
          )}
        </div>
      )}
      {report && (
        <section aria-label="Before publishing" className="space-y-2 rounded-xl border border-border bg-surface-muted p-4 text-sm">
          <h3 className="font-medium">Before publishing (last saved version{report.version_number ? ` ${report.version_number}` : ""})</h3>
          {report.issues.length === 0 ? (
            <p className="text-ok">Nothing missing for any surface.</p>
          ) : (
            <ul className="list-disc space-y-1 pl-5 text-warn">
              {report.issues.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          )}
          <p>
            Access: {report.access.meaning}
            {report.fallback_blocks > 0 ? ` · ${report.fallback_blocks} block(s) use a fallback on the oldest app` : ""}
          </p>
          {report.languages.present && (
            <p>
              Languages: {report.languages.present.map((l) => LANGUAGE[l] ?? l).join(", ")}
              {report.languages.missing?.length ? ` · not yet: ${report.languages.missing.map((l) => LANGUAGE[l] ?? l).join(", ")}` : ""}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
