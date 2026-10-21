// DIAGRAM-ZOOM-01: the full-screen figure viewer's zoom arithmetic (src/lib/zoom.ts). Host-side tests; not device
// evidence of the pinch gesture itself.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { clampView, DOUBLE_TAP_SCALE, MAX_SCALE, panTo, pinchTo, stepZoom, toggleZoom, WHOLE, zoomAbout, type ZoomView } from "../src/lib/zoom.ts";

const stage = { width: 400, height: 300 };
const near = (a: number, b: number) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
/** Where a point of the figure (measured from the stage's centre) appears on screen, from the stage's top left. */
const onScreen = (v: ZoomView, px: number, py: number) => [stage.width / 2 + v.x + v.scale * px, stage.height / 2 + v.y + v.scale * py];

describe("figure zoom", () => {
  it("zooming about a point keeps that point under the fingers", () => {
    const v = zoomAbout(stage, WHOLE, 3, 300, 100);
    const [sx, sy] = onScreen(v, 300 - 200, 100 - 150);
    near(sx, 300);
    near(sy, 100);
    const again = zoomAbout(stage, v, 4.5, 50, 260); // from an already zoomed and moved view
    const px = (50 - 200 - v.x) / v.scale;
    const py = (260 - 150 - v.y) / v.scale;
    const [ax, ay] = onScreen(again, px, py);
    near(ax, 50);
    near(ay, 260);
  });

  it("a pinch is bounded, and settles back inside the stage", () => {
    assert.equal(pinchTo(stage, WHOLE, 20, 200, 150).scale, MAX_SCALE);
    assert.equal(pinchTo(stage, WHOLE, 0.1, 200, 150).scale, 0.9);
    assert.deepEqual(clampView(stage, { scale: 0.9, x: 12, y: -7 }), WHOLE);
    const settled = clampView(stage, { scale: 2, x: 900, y: -900 });
    assert.deepEqual(settled, { scale: 2, x: 200, y: -150 }); // an edge reaches the stage's edge, no empty margin
  });

  it("dragging moves the figure only when it is zoomed in", () => {
    assert.deepEqual(panTo(WHOLE, 40, 30), WHOLE);
    assert.deepEqual(panTo({ scale: 2, x: 10, y: 0 }, 40, -30), { scale: 2, x: 50, y: -30 });
  });

  it("double tap zooms in on the tapped point and back out", () => {
    const zoomed = toggleZoom(stage, WHOLE, 260, 120);
    assert.equal(zoomed.scale, DOUBLE_TAP_SCALE);
    const [sx, sy] = onScreen(zoomed, 60, -30);
    near(sx, 260);
    near(sy, 120);
    assert.deepEqual(toggleZoom(stage, zoomed, 10, 10), WHOLE);
    const corner = toggleZoom(stage, WHOLE, 0, 0); // a corner tap stays within the limits
    assert.deepEqual(corner, clampView(stage, corner));
  });

  it("the + and - buttons step about the centre within 1 to 5 times", () => {
    let v = WHOLE;
    for (let i = 0; i < 10; i++) v = stepZoom(stage, v, 1);
    assert.equal(v.scale, MAX_SCALE);
    assert.equal(v.x, 0);
    for (let i = 0; i < 10; i++) v = stepZoom(stage, v, -1);
    assert.deepEqual(v, WHOLE);
  });

  it("every lesson figure opens the viewer, with a hint for screen readers", () => {
    const blocks = readFileSync(new URL("../src/components/lesson-blocks.tsx", import.meta.url), "utf8");
    assert.match(blocks, /<FigureViewer /);
    assert.match(blocks, /accessibilityHint="Opens the diagram full screen so you can zoom in"/);
    const viewer = readFileSync(new URL("../src/components/figure-viewer.tsx", import.meta.url), "utf8");
    for (const label of ["Zoom out", "Zoom in", "Show the whole diagram", "Close the diagram"]) assert.ok(viewer.includes(`"${label}"`), label);
    assert.match(viewer, /GestureHandlerRootView/); // gestures inside a Modal need their own root
  });
});
