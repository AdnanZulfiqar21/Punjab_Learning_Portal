"use client";

// Written questions and marking rubrics (§20.6). Marks are entered as decimals and stored as integer hundredths
// ("units": 1 mark = 100). The rubric editor shows, live, whether criteria reconcile with the question's maxima;
// the server re-checks everything on submit and publish.
import type { Block } from "@/app/actions/studio";
import { LessonBlocks } from "@/components/lesson-blocks";
import { BlockEditor, normaliseBlocks } from "./block-editor";

type Body = Record<string, unknown>;
type Subpart = { id: string; label: string; blocks: Block[]; max_units: number };
type Written = {
  question_type: "short" | "long";
  stem: Block[];
  subparts: Subpart[];
  max_units: number;
  answer_language: "en" | "ur";
  expected_structures: string[];
  origin: "original_practice" | "authorised_past_paper";
  past_paper_ref?: string | null;
};
type Criterion = {
  id: string;
  subpart_id: string | null;
  description: string;
  max_units: number;
  levels: number[];
  depends_on: string[];
  alternative_group?: string | null;
  evidence?: string | null;
};
type Rubric = {
  question_version_id: string | null;
  authority: "official_scheme" | "practice_rubric";
  authority_ref?: string | null;
  increment_units: number;
  criteria: Criterion[];
  expected_concepts: string[];
  alternative_routes: string[];
  consequential_error_rule?: string | null;
  units_rule?: string | null;
  crossed_out_rule?: string | null;
};
export type QuestionVersionChoice = { id: string; number: number; status: string; body: Body };

const input = "w-full rounded-lg border border-border bg-surface px-3 py-2";
const small = "rounded-md border border-border px-2 py-1 text-xs hover:border-accent disabled:opacity-40";
const toMarks = (u: number) => (u / 100).toString();
const toUnits = (m: string) => Math.round((Number(m) || 0) * 100);
const STRUCTURES = ["diagram", "equation", "table", "chemical_structure", "code"] as const;

export function asWritten(body: Body): Written {
  const b = body as Partial<Written>;
  return {
    question_type: b.question_type ?? "short",
    stem: b.stem ?? [],
    subparts: b.subparts ?? [],
    max_units: b.max_units ?? 0,
    answer_language: b.answer_language ?? "en",
    expected_structures: b.expected_structures ?? [],
    origin: b.origin ?? "original_practice",
    past_paper_ref: b.past_paper_ref ?? null,
  };
}

export function normaliseWritten(body: Body): Body {
  const q = asWritten(body);
  const subparts = q.subparts.map((s) => ({ ...s, blocks: normaliseBlocks(s.blocks) }));
  const out: Body = {
    question_type: q.question_type,
    stem: normaliseBlocks(q.stem),
    subparts,
    max_units: subparts.length ? subparts.reduce((n, s) => n + s.max_units, 0) : q.max_units,
    answer_language: q.answer_language,
    expected_structures: q.expected_structures,
    origin: q.origin,
  };
  if (q.origin === "authorised_past_paper" && q.past_paper_ref) out.past_paper_ref = q.past_paper_ref;
  return out;
}

export function WrittenEditor({ body, onChange }: { body: Body; onChange: (b: Body) => void }) {
  const q = asWritten(body);
  const set = (patch: Partial<Written>) => onChange({ ...q, ...patch });
  const setPart = (i: number, patch: Partial<Subpart>) => set({ subparts: q.subparts.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  const nextId = () => {
    for (let c = 97; c < 123; c++) if (!q.subparts.some((s) => s.id === String.fromCharCode(c))) return String.fromCharCode(c);
    return `p${q.subparts.length + 1}`;
  };
  const total = q.subparts.length ? q.subparts.reduce((n, s) => n + s.max_units, 0) : q.max_units;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Type</span>
          <select value={q.question_type} onChange={(e) => set({ question_type: e.target.value as Written["question_type"] })} className={input}>
            <option value="short">Short answer</option>
            <option value="long">Long answer</option>
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Answer language</span>
          <select value={q.answer_language} onChange={(e) => set({ answer_language: e.target.value as Written["answer_language"] })} className={input}>
            <option value="en">English</option>
            <option value="ur">Urdu</option>
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Total marks</span>
          <input
            type="number"
            step="0.25"
            min="0"
            value={toMarks(total)}
            disabled={q.subparts.length > 0}
            onChange={(e) => set({ max_units: toUnits(e.target.value) })}
            className={input}
            aria-describedby="total-hint"
          />
          <span id="total-hint" className="block text-xs text-muted">
            {q.subparts.length ? "The sum of the subparts." : "Used when the question has no subparts."}
          </span>
        </label>
      </div>
      <section className="space-y-2" aria-labelledby="w-stem">
        <h2 id="w-stem" className="font-medium">
          Question
        </h2>
        <BlockEditor blocks={q.stem} onChange={(stem) => set({ stem })} />
      </section>
      <section className="space-y-3" aria-labelledby="w-parts">
        <h2 id="w-parts" className="font-medium">
          Subparts
        </h2>
        {q.subparts.map((s, i) => (
          <div key={s.id} className="space-y-2 rounded-xl border border-border bg-surface p-3">
            <div className="flex flex-wrap items-end gap-3">
              <label className="space-y-1 text-sm">
                <span className="block text-muted">Label</span>
                <input value={s.label} onChange={(e) => setPart(i, { label: e.target.value })} className={`${input} w-24`} maxLength={20} />
              </label>
              <label className="space-y-1 text-sm">
                <span className="block text-muted">Marks</span>
                <input type="number" step="0.25" min="0" value={toMarks(s.max_units)} onChange={(e) => setPart(i, { max_units: toUnits(e.target.value) })} className={`${input} w-28`} />
              </label>
              <span className="pb-2 font-mono text-xs text-muted">id {s.id}</span>
              <button type="button" className={`${small} ml-auto`} onClick={() => set({ subparts: q.subparts.filter((_, j) => j !== i) })}>
                Remove
              </button>
            </div>
            <BlockEditor blocks={s.blocks} onChange={(blocks) => setPart(i, { blocks })} />
          </div>
        ))}
        <button type="button" className={small} onClick={() => { const id = nextId(); set({ subparts: [...q.subparts, { id, label: `(${id})`, blocks: [], max_units: 100 }] }); }}>
          + Add subpart
        </button>
      </section>
      <fieldset className="space-y-2">
        <legend className="font-medium">Structures the answer may need</legend>
        <div className="flex flex-wrap gap-3 text-sm">
          {STRUCTURES.map((st) => (
            <label key={st} className="flex items-center gap-2 capitalize">
              <input
                type="checkbox"
                checked={q.expected_structures.includes(st)}
                onChange={(e) => set({ expected_structures: e.target.checked ? [...q.expected_structures, st] : q.expected_structures.filter((x) => x !== st) })}
              />
              {st.replace("_", " ")}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Origin</span>
          <select value={q.origin} onChange={(e) => set({ origin: e.target.value as Written["origin"] })} className={input}>
            <option value="original_practice">Original practice question</option>
            <option value="authorised_past_paper">Authorised past-paper question</option>
          </select>
        </label>
        {q.origin === "authorised_past_paper" && (
          <label className="space-y-1 text-sm">
            <span className="block font-medium">Where reuse is authorised</span>
            <input value={q.past_paper_ref ?? ""} onChange={(e) => set({ past_paper_ref: e.target.value })} className={input} maxLength={300} />
          </label>
        )}
      </div>
    </div>
  );
}

export function WrittenPreview({ body }: { body: Body }) {
  const q = asWritten(body);
  const total = q.subparts.length ? q.subparts.reduce((n, s) => n + s.max_units, 0) : q.max_units;
  return (
    <div className="space-y-3">
      <LessonBlocks blocks={q.stem} headingOffset={1} />
      {q.subparts.map((s) => (
        <div key={s.id} className="flex gap-3">
          <span className="font-medium">{s.label}</span>
          <div className="flex-1">
            <LessonBlocks blocks={s.blocks} headingOffset={2} />
          </div>
          <span className="text-sm text-muted">[{toMarks(s.max_units)}]</span>
        </div>
      ))}
      <p className="text-sm text-muted">
        {q.question_type === "long" ? "Long" : "Short"} answer · {toMarks(total)} marks · answer in {q.answer_language === "ur" ? "Urdu" : "English"}
      </p>
    </div>
  );
}

// ------------------------------------------------------------------ rubric
export function asRubric(body: Body): Rubric {
  const b = body as Partial<Rubric>;
  return {
    question_version_id: b.question_version_id ?? null,
    authority: b.authority ?? "practice_rubric",
    authority_ref: b.authority_ref ?? null,
    increment_units: b.increment_units ?? 50,
    criteria: (b.criteria ?? []).map((c) => ({ ...c, depends_on: c.depends_on ?? [], subpart_id: c.subpart_id ?? null })),
    expected_concepts: b.expected_concepts ?? [],
    alternative_routes: b.alternative_routes ?? [],
    consequential_error_rule: b.consequential_error_rule ?? null,
    units_rule: b.units_rule ?? null,
    crossed_out_rule: b.crossed_out_rule ?? null,
  };
}

export function normaliseRubric(body: Body): Body {
  const r = asRubric(body);
  const clean = (s?: string | null) => (s && s.trim() ? s.trim() : undefined);
  return {
    question_version_id: r.question_version_id,
    authority: r.authority,
    authority_ref: clean(r.authority_ref),
    increment_units: r.increment_units,
    criteria: r.criteria.map((c) => ({
      id: c.id,
      subpart_id: c.subpart_id,
      description: c.description,
      max_units: c.max_units,
      levels: [...new Set(c.levels)].sort((a, b) => a - b),
      depends_on: c.depends_on.filter(Boolean),
      alternative_group: clean(c.alternative_group),
      evidence: clean(c.evidence),
    })),
    expected_concepts: r.expected_concepts.map((x) => x.trim()).filter(Boolean),
    alternative_routes: r.alternative_routes.map((x) => x.trim()).filter(Boolean),
    consequential_error_rule: clean(r.consequential_error_rule),
    units_rule: clean(r.units_rule),
    crossed_out_rule: clean(r.crossed_out_rule),
  };
}

/** Creditable units per slot, counting each alternative group once at its largest criterion (mirrors the API). */
function slotTotals(r: Rubric): Map<string | null, number> {
  const totals = new Map<string | null, number>();
  const groups = new Map<string, { slot: string | null; cap: number }>();
  for (const c of r.criteria) {
    if (c.alternative_group) {
      const key = `${c.subpart_id ?? ""}::${c.alternative_group}`;
      const g = groups.get(key);
      groups.set(key, { slot: c.subpart_id, cap: Math.max(g?.cap ?? 0, c.max_units) });
    } else totals.set(c.subpart_id, (totals.get(c.subpart_id) ?? 0) + c.max_units);
  }
  for (const g of groups.values()) totals.set(g.slot, (totals.get(g.slot) ?? 0) + g.cap);
  return totals;
}

export function RubricEditor({
  body,
  onChange,
  versions,
}: {
  body: Body;
  onChange: (b: Body) => void;
  versions: QuestionVersionChoice[];
}) {
  const r = asRubric(body);
  const set = (patch: Partial<Rubric>) => onChange({ ...r, ...patch });
  const setC = (i: number, patch: Partial<Criterion>) => set({ criteria: r.criteria.map((c, j) => (j === i ? { ...c, ...patch } : c)) });
  const qv = versions.find((v) => v.id === r.question_version_id);
  const q = qv ? asWritten(qv.body) : null;
  const slots: { id: string | null; label: string; max: number }[] = q
    ? q.subparts.length
      ? q.subparts.map((s) => ({ id: s.id, label: s.label, max: s.max_units }))
      : [{ id: null, label: "Whole question", max: q.max_units }]
    : [];
  const totals = slotTotals(r);
  const nextId = () => {
    for (let n = 1; ; n++) if (!r.criteria.some((c) => c.id === `c${n}`)) return `c${n}`;
  };
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="space-y-1 text-sm sm:col-span-3">
          <span className="block font-medium">Question version this rubric marks</span>
          <select value={r.question_version_id ?? ""} onChange={(e) => set({ question_version_id: e.target.value || null })} className={input}>
            <option value="">Choose a version</option>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                Version {v.number} ({v.status.replace("_", " ")})
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Authority</span>
          <select value={r.authority} onChange={(e) => set({ authority: e.target.value as Rubric["authority"] })} className={input}>
            <option value="practice_rubric">Practice rubric (teacher-authored)</option>
            <option value="official_scheme">Official marking scheme</option>
          </select>
        </label>
        {r.authority === "official_scheme" && (
          <label className="space-y-1 text-sm">
            <span className="block font-medium">Where the scheme is published</span>
            <input value={r.authority_ref ?? ""} onChange={(e) => set({ authority_ref: e.target.value })} className={input} maxLength={300} />
          </label>
        )}
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Smallest award</span>
          <select value={r.increment_units} onChange={(e) => set({ increment_units: Number(e.target.value) })} className={input}>
            <option value={100}>1 mark</option>
            <option value={50}>0.5 mark</option>
            <option value={25}>0.25 mark</option>
          </select>
        </label>
      </div>

      {slots.length > 0 && (
        <table className="w-full text-sm" aria-label="Reconciliation with the question">
          <thead>
            <tr className="text-left text-muted">
              <th className="py-1">Slot</th>
              <th>Question maximum</th>
              <th>Rubric credit</th>
            </tr>
          </thead>
          <tbody>
            {slots.map((s) => {
              const got = totals.get(s.id) ?? 0;
              return (
                <tr key={s.id ?? "whole"} className={got === s.max ? "text-ok" : "text-danger"}>
                  <td className="py-1">{s.label}</td>
                  <td>{toMarks(s.max)}</td>
                  <td>
                    {toMarks(got)} {got === s.max ? "✓" : "(must match)"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <section className="space-y-3" aria-labelledby="r-crit">
        <h2 id="r-crit" className="font-medium">
          Criteria
        </h2>
        {r.criteria.map((c, i) => (
          <div key={c.id} className="space-y-2 rounded-xl border border-border bg-surface p-3">
            <div className="flex flex-wrap items-end gap-3">
              <span className="pb-2 font-mono text-xs text-muted">id {c.id}</span>
              <label className="space-y-1 text-sm">
                <span className="block text-muted">Slot</span>
                <select value={c.subpart_id ?? ""} onChange={(e) => setC(i, { subpart_id: e.target.value || null })} className={input}>
                  {slots.map((s) => (
                    <option key={s.id ?? "whole"} value={s.id ?? ""}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="block text-muted">Maximum</span>
                <input type="number" step="0.25" min="0" value={toMarks(c.max_units)} onChange={(e) => setC(i, { max_units: toUnits(e.target.value) })} className={`${input} w-24`} />
              </label>
              <label className="space-y-1 text-sm">
                <span className="block text-muted">Permitted awards (marks, comma separated)</span>
                <input
                  value={c.levels.map(toMarks).join(", ")}
                  onChange={(e) => setC(i, { levels: e.target.value.split(",").map((x) => x.trim()).filter(Boolean).map(toUnits) })}
                  className={`${input} w-56`}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="block text-muted">Alternative group</span>
                <input value={c.alternative_group ?? ""} onChange={(e) => setC(i, { alternative_group: e.target.value })} className={`${input} w-28`} maxLength={12} />
              </label>
              <button type="button" className={`${small} ml-auto`} onClick={() => set({ criteria: r.criteria.filter((_, j) => j !== i) })}>
                Remove
              </button>
            </div>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">What earns credit (including accepted equivalent wording)</span>
              <textarea value={c.description} onChange={(e) => setC(i, { description: e.target.value })} rows={2} className={input} maxLength={2000} />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Depends on (criterion ids, comma separated)</span>
              <input value={c.depends_on.join(", ")} onChange={(e) => setC(i, { depends_on: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} className={input} />
            </label>
          </div>
        ))}
        <button
          type="button"
          className={small}
          onClick={() =>
            set({ criteria: [...r.criteria, { id: nextId(), subpart_id: slots[0]?.id ?? null, description: "", max_units: 100, levels: [0, 100], depends_on: [] }] })
          }
        >
          + Add criterion
        </button>
      </section>

      <section className="grid gap-4 sm:grid-cols-2" aria-label="Marking rules">
        <label className="space-y-1 text-sm sm:col-span-2">
          <span className="block font-medium">Expected concepts (one per line)</span>
          <textarea value={r.expected_concepts.join("\n")} onChange={(e) => set({ expected_concepts: e.target.value.split("\n") })} rows={3} className={input} />
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span className="block font-medium">Valid alternative routes (one per line)</span>
          <textarea value={r.alternative_routes.join("\n")} onChange={(e) => set({ alternative_routes: e.target.value.split("\n") })} rows={2} className={input} />
        </label>
        {(
          [
            ["consequential_error_rule", "Consequential (carried-forward) errors"],
            ["units_rule", "Units and significant figures"],
            ["crossed_out_rule", "Crossed-out work"],
          ] as const
        ).map(([k, label]) => (
          <label key={k} className="space-y-1 text-sm">
            <span className="block font-medium">{label}</span>
            <textarea value={r[k] ?? ""} onChange={(e) => set({ [k]: e.target.value } as Partial<Rubric>)} rows={2} className={input} maxLength={1000} />
          </label>
        ))}
      </section>
    </div>
  );
}

export function RubricPreview({ body }: { body: Body }) {
  const r = asRubric(body);
  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted">
        {r.authority === "official_scheme" ? `Official scheme (${r.authority_ref ?? "reference missing"})` : "Practice rubric (teacher-authored)"} · smallest award{" "}
        {toMarks(r.increment_units)}
      </p>
      <ol className="space-y-2">
        {r.criteria.map((c) => (
          <li key={c.id} className="rounded-lg border border-border px-3 py-2">
            <span className="font-mono text-xs text-muted">
              {c.id}
              {c.subpart_id ? ` · part ${c.subpart_id}` : ""}
              {c.alternative_group ? ` · alternative ${c.alternative_group}` : ""}
            </span>
            <p>{c.description}</p>
            <p className="text-muted">
              Up to {toMarks(c.max_units)} · awards {c.levels.map(toMarks).join(", ")}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function writtenSections(kind: string, body: Body): { label: string; text: string }[] {
  if (kind === "rubric") {
    const r = asRubric(body);
    return [{ label: "Rubric settings", text: JSON.stringify([r.question_version_id, r.authority, r.increment_units]) }, ...r.criteria.map((c) => ({ label: `Criterion ${c.id}`, text: JSON.stringify(c) }))];
  }
  const q = asWritten(body);
  return [{ label: "Question", text: JSON.stringify(q.stem) }, ...q.subparts.map((s) => ({ label: `Part ${s.id}`, text: JSON.stringify(s) }))];
}
