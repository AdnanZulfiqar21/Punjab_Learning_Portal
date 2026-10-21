// DIAGRAM-ZOOM-01: the arithmetic of the full-screen figure viewer. Pure functions marked as worklets, so the gestures
// run them on the UI thread and the host tests run them in Node. The figure is transformed as translate, then scale,
// about the stage's centre, so positions here are measured from that centre: screen = offset + scale * point.

export const MIN_SCALE = 1;
export const MAX_SCALE = 5;
/** A pinch may undershoot a little before the view settles back to the whole figure. */
export const PINCH_FLOOR = 0.9;
export const DOUBLE_TAP_SCALE = 2.5;
/** One press of the + or - button. */
export const STEP = 1.5;

export type Box = { width: number; height: number };
export type ZoomView = { scale: number; x: number; y: number };

export const WHOLE: ZoomView = { scale: 1, x: 0, y: 0 };

export function clampScale(scale: number): number {
  "worklet";
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}

/** How far the figure may move at this scale before one of its edges comes inside the stage. */
export function limits(stage: Box, scale: number): { x: number; y: number } {
  "worklet";
  return { x: Math.max(0, (stage.width * (scale - 1)) / 2), y: Math.max(0, (stage.height * (scale - 1)) / 2) };
}

/** The nearest allowed view: scale within 1 to 5 and no empty margin pulled into the stage. */
export function clampView(stage: Box, view: ZoomView): ZoomView {
  "worklet";
  const scale = clampScale(view.scale);
  const l = limits(stage, scale);
  // + 0 turns -0 into 0, so a settled view compares equal to the whole figure
  return { scale, x: Math.min(l.x, Math.max(-l.x, view.x)) + 0, y: Math.min(l.y, Math.max(-l.y, view.y)) + 0 };
}

/** Change the scale while the point under (fx, fy), measured from the stage's top left, stays where it is. */
export function zoomAbout(stage: Box, from: ZoomView, scale: number, fx: number, fy: number): ZoomView {
  "worklet";
  const cx = fx - stage.width / 2;
  const cy = fy - stage.height / 2;
  const k = scale / from.scale;
  return { scale, x: cx - (cx - from.x) * k, y: cy - (cy - from.y) * k };
}

/** A pinch in progress: free within 0.9 to 5, about the fingers' focal point. */
export function pinchTo(stage: Box, start: ZoomView, pinchScale: number, fx: number, fy: number): ZoomView {
  "worklet";
  const scale = Math.min(MAX_SCALE, Math.max(PINCH_FLOOR, start.scale * pinchScale));
  return zoomAbout(stage, start, scale, fx, fy);
}

/** A drag: moves the figure only when it is zoomed in. */
export function panTo(start: ZoomView, dx: number, dy: number): ZoomView {
  "worklet";
  return start.scale > 1 ? { scale: start.scale, x: start.x + dx, y: start.y + dy } : start;
}

/** Double tap: zoom in about the tapped point, or back to the whole figure. */
export function toggleZoom(stage: Box, from: ZoomView, fx: number, fy: number): ZoomView {
  "worklet";
  if (from.scale > 1.01) return WHOLE;
  return clampView(stage, zoomAbout(stage, from, DOUBLE_TAP_SCALE, fx, fy));
}

/** The + and - buttons: one step about the centre of the stage. */
export function stepZoom(stage: Box, from: ZoomView, direction: 1 | -1): ZoomView {
  "worklet";
  const scale = clampScale(direction > 0 ? from.scale * STEP : from.scale / STEP);
  return clampView(stage, zoomAbout(stage, from, scale, stage.width / 2, stage.height / 2));
}
