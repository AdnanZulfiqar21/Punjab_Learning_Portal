// REGION-MAP-01 (W03.S2.T2): an area kept in the original page's coordinates (x, y, w, h fractions of the upright
// original) placed on the page as currently shown, with its turn, trim and straightening applied. The same mapping as
// `evidence.from_source` in the API, so an area drawn before the page was turned is still shown in the right place.
export type Box = [number, number, number, number];

type Transform = {
  rotate?: number | null;
  crop?: number[] | null;
  straighten?: number | string | null;
  aspect?: number | null;
  shown_crop?: number[] | null;
};

function straightenRegion([x, y, w, h]: Box, angle: number, aspect: number): Box {
  const t = (angle * Math.PI) / 180;
  const c = Math.cos(t);
  const s = Math.sin(t);
  const w0 = aspect;
  const h0 = 1;
  const shownW = w0 * Math.abs(c) + h0 * Math.abs(s);
  const shownH = w0 * Math.abs(s) + h0 * Math.abs(c);
  const xs: number[] = [];
  const ys: number[] = [];
  for (const [u, v] of [
    [x, y],
    [x + w, y],
    [x, y + h],
    [x + w, y + h],
  ]) {
    const ox = u * w0 - w0 / 2;
    const oy = v * h0 - h0 / 2;
    xs.push((c * ox + s * oy + shownW / 2) / shownW);
    ys.push((-s * ox + c * oy + shownH / 2) / shownH);
  }
  const left = Math.max(0, Math.min(...xs));
  const top = Math.max(0, Math.min(...ys));
  return [left, top, Math.max(0, Math.min(1, Math.max(...xs)) - left), Math.max(0, Math.min(1, Math.max(...ys)) - top)];
}

/** Where an area of the original appears on the page as shown; null when it can't be placed or is trimmed away. */
export function fromSource(source: number[], transform: Transform | null | undefined): Box | null {
  if (source.length !== 4) return null;
  let [x, y, w, h] = source;
  const t = transform ?? {};
  const [cx, cy, cw, ch] = t.crop && t.crop.length === 4 ? t.crop : [0, 0, 1, 1];
  [x, y, w, h] = [(x - cx) / cw, (y - cy) / ch, w / cw, h / ch];
  const rotate = t.rotate ?? 0;
  if (rotate === 90) [x, y, w, h] = [1 - y - h, x, h, w];
  else if (rotate === 180) [x, y] = [1 - x - w, 1 - y - h];
  else if (rotate === 270) [x, y, w, h] = [y, 1 - x - w, h, w];
  const angle = typeof t.straighten === "number" ? t.straighten : 0;
  if (angle) {
    if (!t.aspect) return null;
    [x, y, w, h] = straightenRegion([x, y, w, h], angle, t.aspect);
    if (t.shown_crop && t.shown_crop.length === 4) {
      const [sx, sy, sw, sh] = t.shown_crop;
      [x, y, w, h] = [(x - sx) / sw, (y - sy) / sh, w / sw, h / sh];
    }
  }
  const left = Math.max(0, x);
  const top = Math.max(0, y);
  const right = Math.min(1, x + w);
  const bottom = Math.min(1, y + h);
  if (right <= left || bottom <= top) return null;
  return [left, top, right - left, bottom - top];
}

type SlotLike = { pages: string[]; regions?: { page: string }[] };

/** Pages used by more than one answer where at least one of them doesn't mark its area there (as the API decides). */
export function ambiguousPages(slots: Record<string, SlotLike>): string[] {
  const users = new Map<string, string[]>();
  for (const [key, slot] of Object.entries(slots)) for (const p of slot.pages) users.set(p, [...(users.get(p) ?? []), key]);
  const out: string[] = [];
  for (const [p, keys] of users) {
    if (keys.length > 1 && keys.some((k) => !(slots[k].regions ?? []).some((r) => r.page === p))) out.push(p);
  }
  return out.sort();
}
