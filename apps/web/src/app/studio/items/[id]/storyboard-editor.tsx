"use client";

// P07.S4.T1/T2: scene-by-scene storyboard. Teaching constraints (narration, on-screen text, equations, claims with
// source references) are kept apart from creative direction (visual, transition, assets).
type Body = Record<string, unknown>;
type Claim = { text: string; source_ref: number };
type Scene = {
  id: string;
  start_s: number;
  end_s: number;
  visual: string;
  on_screen_text: string;
  narration: string;
  transition: string;
  equations: string[];
  assets: string[];
  accessibility: string;
  claims: Claim[];
};
type Storyboard = {
  objective: string;
  outcome: string;
  prerequisites: string[];
  duration_s: number | null;
  creative_direction: string;
  scenes: Scene[];
};

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const lines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

export function readStoryboard(body: Body): Storyboard {
  const scenes = Array.isArray(body.scenes) ? (body.scenes as Partial<Scene>[]) : [];
  return {
    objective: String(body.objective ?? ""),
    outcome: String(body.outcome ?? ""),
    prerequisites: Array.isArray(body.prerequisites) ? (body.prerequisites as string[]) : [],
    duration_s: typeof body.duration_s === "number" ? body.duration_s : null,
    creative_direction: String(body.creative_direction ?? ""),
    scenes: scenes.map((s, i) => ({
      id: String(s.id ?? `s${i + 1}`),
      start_s: Number(s.start_s ?? 0),
      end_s: Number(s.end_s ?? 0),
      visual: String(s.visual ?? ""),
      on_screen_text: String(s.on_screen_text ?? ""),
      narration: String(s.narration ?? ""),
      transition: String(s.transition ?? ""),
      equations: Array.isArray(s.equations) ? s.equations : [],
      assets: Array.isArray(s.assets) ? s.assets : [],
      accessibility: String(s.accessibility ?? ""),
      claims: Array.isArray(s.claims) ? s.claims : [],
    })),
  };
}

export function normaliseStoryboard(body: Body): Body {
  return readStoryboard(body) as unknown as Body;
}

export function StoryboardEditor({ body, onChange, refCount }: { body: Body; onChange: (b: Body) => void; refCount: number }) {
  const sb = readStoryboard(body);
  const set = (next: Partial<Storyboard>) => onChange({ ...sb, ...next } as unknown as Body);
  const setScene = (i: number, next: Partial<Scene>) => set({ scenes: sb.scenes.map((s, k) => (k === i ? { ...s, ...next } : s)) });
  const addScene = () => {
    const start = sb.scenes.length ? sb.scenes[sb.scenes.length - 1].end_s : 0;
    set({
      scenes: [
        ...sb.scenes,
        { id: `s${sb.scenes.length + 1}`, start_s: start, end_s: start + 20, visual: "", on_screen_text: "", narration: "", transition: "", equations: [], assets: [], accessibility: "", claims: [] },
      ],
    });
  };
  return (
    <div className="space-y-5">
      <section aria-labelledby="sb-goals" className="space-y-2">
        <h2 id="sb-goals" className="font-semibold">
          Goals
        </h2>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Learning objective</span>
          <textarea value={sb.objective} onChange={(e) => set({ objective: e.target.value })} rows={2} maxLength={500} className={field} />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Lesson outcome</span>
          <textarea value={sb.outcome} onChange={(e) => set({ outcome: e.target.value })} rows={2} maxLength={500} className={field} />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Prerequisites (one per line)</span>
          <textarea value={sb.prerequisites.join("\n")} onChange={(e) => set({ prerequisites: lines(e.target.value) })} rows={2} className={field} />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Target duration (seconds)</span>
          <input type="number" min={10} max={7200} value={sb.duration_s ?? ""} onChange={(e) => set({ duration_s: e.target.value ? Number(e.target.value) : null })} className={field} />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Creative direction (style, pacing, voice)</span>
          <textarea value={sb.creative_direction} onChange={(e) => set({ creative_direction: e.target.value })} rows={2} maxLength={2000} className={field} />
        </label>
      </section>
      <section aria-labelledby="sb-scenes" className="space-y-3">
        <h2 id="sb-scenes" className="font-semibold">
          Scenes
        </h2>
        {sb.scenes.map((s, i) => (
          <fieldset key={i} className="space-y-2 rounded-lg border border-border p-3">
            <legend className="px-1 text-sm font-medium">
              Scene {i + 1} · {s.start_s}s to {s.end_s}s
            </legend>
            <div className="grid gap-2 sm:grid-cols-3">
              <label className="space-y-1 text-sm">
                <span>Scene ID</span>
                <input value={s.id} onChange={(e) => setScene(i, { id: e.target.value })} maxLength={20} className={field} />
              </label>
              <label className="space-y-1 text-sm">
                <span>Starts (s)</span>
                <input type="number" min={0} value={s.start_s} onChange={(e) => setScene(i, { start_s: Number(e.target.value) })} className={field} />
              </label>
              <label className="space-y-1 text-sm">
                <span>Ends (s)</span>
                <input type="number" min={1} value={s.end_s} onChange={(e) => setScene(i, { end_s: Number(e.target.value) })} className={field} />
              </label>
            </div>
            <label className="block space-y-1 text-sm">
              <span>Narration</span>
              <textarea value={s.narration} onChange={(e) => setScene(i, { narration: e.target.value })} rows={3} maxLength={4000} className={field} />
            </label>
            <label className="block space-y-1 text-sm">
              <span>On-screen text</span>
              <input value={s.on_screen_text} onChange={(e) => setScene(i, { on_screen_text: e.target.value })} maxLength={500} className={field} />
            </label>
            <label className="block space-y-1 text-sm">
              <span>Equations (one per line)</span>
              <textarea value={s.equations.join("\n")} onChange={(e) => setScene(i, { equations: lines(e.target.value) })} rows={2} className={field} />
            </label>
            <label className="block space-y-1 text-sm">
              <span>Visual</span>
              <textarea value={s.visual} onChange={(e) => setScene(i, { visual: e.target.value })} rows={2} maxLength={2000} className={field} />
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span>Transition</span>
                <input value={s.transition} onChange={(e) => setScene(i, { transition: e.target.value })} maxLength={200} className={field} />
              </label>
              <label className="space-y-1 text-sm">
                <span>Assets (one per line)</span>
                <textarea value={s.assets.join("\n")} onChange={(e) => setScene(i, { assets: lines(e.target.value) })} rows={2} className={field} />
              </label>
            </div>
            <label className="block space-y-1 text-sm">
              <span>Accessibility notes (describe visuals and equations)</span>
              <textarea value={s.accessibility} onChange={(e) => setScene(i, { accessibility: e.target.value })} rows={2} maxLength={1000} className={field} />
            </label>
            <div className="space-y-1 text-sm">
              <span className="font-medium">Claims taught in this scene</span>
              {s.claims.map((c, k) => (
                <div key={k} className="flex flex-wrap gap-2">
                  <input
                    aria-label={`Scene ${i + 1} claim ${k + 1}`}
                    value={c.text}
                    onChange={(e) => setScene(i, { claims: s.claims.map((x, j) => (j === k ? { ...x, text: e.target.value } : x)) })}
                    maxLength={500}
                    className={`${field} min-w-0 flex-1`}
                  />
                  <select
                    aria-label={`Scene ${i + 1} claim ${k + 1} source`}
                    value={c.source_ref}
                    onChange={(e) => setScene(i, { claims: s.claims.map((x, j) => (j === k ? { ...x, source_ref: Number(e.target.value) } : x)) })}
                    className="rounded-lg border border-border bg-surface px-2 py-2"
                  >
                    {Array.from({ length: Math.max(refCount, 1) }, (_, r) => (
                      <option key={r} value={r}>
                        Source {r + 1}
                      </option>
                    ))}
                  </select>
                  <button type="button" onClick={() => setScene(i, { claims: s.claims.filter((_, j) => j !== k) })} className="rounded-lg border border-border px-2 text-sm">
                    Remove
                  </button>
                </div>
              ))}
              <button type="button" onClick={() => setScene(i, { claims: [...s.claims, { text: "", source_ref: 0 }] })} className="rounded-lg border border-border bg-surface px-3 py-1 text-sm hover:border-accent">
                + Add claim
              </button>
            </div>
            <button type="button" onClick={() => set({ scenes: sb.scenes.filter((_, k) => k !== i) })} className="text-sm text-danger underline">
              Remove scene {i + 1}
            </button>
          </fieldset>
        ))}
        <button type="button" onClick={addScene} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent">
          + Add scene
        </button>
      </section>
    </div>
  );
}

export function StoryboardPreview({ body }: { body: Body }) {
  const sb = readStoryboard(body);
  return (
    <div className="space-y-3 text-sm">
      <p>
        <span className="font-medium">Objective:</span> {sb.objective || "—"}
      </p>
      <p>
        <span className="font-medium">Outcome:</span> {sb.outcome || "—"}
      </p>
      <ol className="space-y-2">
        {sb.scenes.map((s, i) => (
          <li key={i} className="rounded-lg border border-border p-3">
            <p className="font-medium">
              {s.id} · {s.start_s}s to {s.end_s}s
            </p>
            <p>{s.narration}</p>
            {s.claims.length > 0 && <p className="text-muted">Claims: {s.claims.map((c) => `${c.text} [source ${c.source_ref + 1}]`).join("; ")}</p>}
            {s.visual && <p className="text-muted">Visual: {s.visual}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}
