// Renders the original figures for the Biology XI Chapter 1 pilot (MODEL3D-01, FIGURES-01).
//
//   node content/tools/figures/render.mjs            # everything
//   node content/tools/figures/render.mjs svg         # the vector diagrams only
//   node content/tools/figures/render.mjs svg chemistry   # another subject (default biology)
//   node content/tools/figures/render.mjs scenes      # the 3D models only (poster + turntable stills)
//   node content/tools/figures/render.mjs scenes physics 11   # one book's 3D models (scenes/c11-phy-ch<N>_<model>.js)
//   FIGURES_ONLY=c11-chem-ch1-fig-a,c11-chem-ch1-fig-b node content/tools/figures/render.mjs svg chemistry 11
//                                                      # only these diagrams (no re-encoding of the others' PNGs)
//   FIGURES_PRUNE=1 node content/tools/figures/render.mjs svg chemistry 11
//                                                      # also drop retired diagrams: manifest entries and PNGs whose svg/ file is gone
//
// Vector diagrams (svg/*.svg) become PNGs at 2x. Each three.js scene (scenes/*.js) becomes a labelled poster and
// FRAMES evenly spaced stills of one full turn about its axis, drawn by headless Chromium (SwiftShader WebGL) with
// three.js from apps/web. Output: content/lessons/xi/biology/figures/, plus figures.json, which the import tool turns
// into a media-pack manifest. Nothing here touches the textbook's own images.
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync, statSync, unlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..", "..", "..");
const require = createRequire(join(root, "apps", "web", "package.json"));
const { chromium } = require("@playwright/test");
const THREE_PATH = join(root, "apps", "web", "node_modules", "three", "build", "three.module.js");
// Subject (argv[3], default biology) and grade (argv[4], 11 or 12, default 11): figures live under
// content/lessons/<xi|xii>/<subject>/figures and only the svg/ files whose id starts with the book's prefix
// (c11-bio-, c12-chem-, ...) are rendered. Class XI and XII books never share a folder or prefix.
const SUBJECTS = { biology: { code: "bio", name: "Biology" }, chemistry: { code: "chem", name: "Chemistry" }, physics: { code: "phy", name: "Physics" }, computer_science: { code: "cs", name: "Computer Science" } };
const GRADES = { 11: { dir: "xi", label: "XI" }, 12: { dir: "xii", label: "XII" } };
const subject = process.argv[3] ?? "biology";
const grade = process.argv[4] ?? "11";
if (!SUBJECTS[subject]) throw new Error(`unknown subject ${subject}; one of ${Object.keys(SUBJECTS).join(", ")}`);
if (!GRADES[grade]) throw new Error(`unknown grade ${grade}; one of ${Object.keys(GRADES).join(", ")}`);
const PREFIX = `c${grade}-${SUBJECTS[subject].code}-`;
const BOOK = `Class ${GRADES[grade].label} ${SUBJECTS[subject].name}`;
const OUT = join(root, "content", "lessons", GRADES[grade].dir, subject, "figures");
const FRAMES = 16;
const POSTER = { w: 1200, h: 900 };
const FRAME = { w: 640, h: 480 };
const PROVENANCE = {
  author: "Punjab Learning Portal content team (drafted with Claude)",
  licence: "Original work for the Punjab Learning Portal; not a textbook image",
};

const PAGE = `<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body{margin:0;background:#fff;font-family:"Segoe UI",Helvetica,Arial,sans-serif}
  #stage{position:relative;background:#fff}
  canvas{display:block}
  .lbl{position:absolute;transform:translate(-50%,-50%);font-size:26px;font-weight:600;color:#14181f;background:rgba(255,255,255,.92);
       border:2px solid #0f7a62;border-radius:10px;padding:4px 12px;white-space:nowrap;line-height:1.2}
  svg.leaders{position:absolute;inset:0;pointer-events:none}
</style></head>
<body><div id="stage"><canvas id="c"></canvas><svg class="leaders" id="leaders"></svg><div id="labels"></div></div>
<script type="module">
  import * as THREE from "./three.module.js";
  import * as Scene from "./scene.js";
  const built = Scene.build(THREE);
  window.__title = Scene.title;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xffffff);
  const pivot = new THREE.Group();
  pivot.add(built.group);
  scene.add(pivot);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8e2ea, 1.1));
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(4, 7, 6); scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, 0.5); fill.position.set(-6, 2, -3); scene.add(fill);
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const canvas = document.getElementById("c");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true, alpha: false });
  const cam = new THREE.PerspectiveCamera(built.camera.fov ?? 40, 4 / 3, 0.1, 100);
  cam.position.set(...built.camera.position);
  cam.lookAt(new THREE.Vector3(...(built.camera.lookAt ?? [0, 0, 0])));
  window.__render = (w, h, angle, withLabels) => {
    document.getElementById("stage").style.width = w + "px";
    document.getElementById("stage").style.height = h + "px";
    renderer.setPixelRatio(1);
    renderer.setSize(w, h, true);
    cam.aspect = w / h; cam.updateProjectionMatrix();
    pivot.rotation.set(0, 0, 0);
    if (built.turntableAxis === "x") pivot.rotation.x = angle; else pivot.rotation.y = angle;
    renderer.render(scene, cam);
    const labels = document.getElementById("labels"); labels.innerHTML = "";
    const leaders = document.getElementById("leaders"); leaders.innerHTML = "";
    leaders.setAttribute("width", w); leaders.setAttribute("height", h);
    if (!withLabels) return;
    const placed = [];
    for (const l of built.labels ?? []) {
      const v = new THREE.Vector3(...l.at).project(cam);
      const x = (v.x + 1) / 2 * w, y = (1 - v.y) / 2 * h;
      const dx = l.anchor === "left" ? -150 : l.anchor === "right" ? 150 : 0;
      let dy = l.anchor === "above" ? -70 : l.anchor === "below" ? 60 : 0;
      let lx = x + dx, ly = y + dy;
      // nudge labels apart vertically when they would overlap
      for (const p of placed) { if (Math.abs(p.x - lx) < 240 && Math.abs(p.y - ly) < 40) ly = p.y + 42; }
      placed.push({ x: lx, y: ly });
      lx = Math.min(Math.max(lx, 110), w - 110); ly = Math.min(Math.max(ly, 24), h - 24);
      const div = document.createElement("div"); div.className = "lbl"; div.textContent = l.text;
      div.style.left = lx + "px"; div.style.top = ly + "px"; labels.appendChild(div);
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", x); line.setAttribute("y1", y); line.setAttribute("x2", lx); line.setAttribute("y2", ly);
      line.setAttribute("stroke", "#4b5563"); line.setAttribute("stroke-width", "2.5"); leaders.appendChild(line);
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", x); dot.setAttribute("cy", y); dot.setAttribute("r", "5"); dot.setAttribute("fill", "#4b5563"); leaders.appendChild(dot);
    }
  };
  window.__ready = true;
</script></body></html>`;

const what = process.argv[2] ?? "all";
mkdirSync(OUT, { recursive: true });
const manifest = [];

const browser = await chromium.launch({
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl"],
});

const ONLY = new Set((process.env.FIGURES_ONLY ?? "").split(",").map((s) => s.trim()).filter(Boolean));
if (what === "all" || what === "svg") {
  const page = await browser.newPage({ viewport: { width: 1000, height: 1000 }, deviceScaleFactor: 2 });
  const files = readdirSync(join(here, "svg")).filter((f) => f.endsWith(".svg") && f.startsWith(PREFIX) && (!ONLY.size || ONLY.has(f.replace(/\.svg$/, ""))));
  if (ONLY.size && files.length !== ONLY.size) throw new Error(`FIGURES_ONLY names ${ONLY.size} diagrams but ${files.length} svg/ files match`);
  for (const file of files.sort()) {
    const id = file.replace(/\.svg$/, "");
    const svg = readFileSync(join(here, "svg", file), "utf8");
    const m = svg.match(/viewBox="0 0 (\d+) (\d+)"/);
    const [w, h] = m ? [Number(m[1]), Number(m[2])] : [1000, 1000];
    await page.setViewportSize({ width: w, height: h });
    await page.setContent(`<!doctype html><html><body style="margin:0;background:#fff">${svg}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    const out = join(OUT, `${id}.png`);
    await page.locator("svg").screenshot({ path: out, type: "png", omitBackground: false });
    manifest.push({
      external_id: id,
      kind: "image",
      title: id.replace(new RegExp(`^${PREFIX}ch\\d+-fig-`), "Figure: ").replace(/-/g, " "),
      file: `figures/${id}.png`,
      provenance: { ...PROVENANCE, source: `Original vector diagram drawn from the ${BOOK} text, chapter ${(id.match(new RegExp(`^${PREFIX}ch(\\d+)-`)) ?? [])[1] ?? "?"} (svg/${file})`, tool: "SVG rendered by headless Chromium" },
      bytes: statSync(out).size,
    });
    console.log("svg", id, statSync(out).size, "bytes");
  }
  await page.close();
}

if (what === "all" || what === "scenes") {
  const threeSource = readFileSync(THREE_PATH, "utf8");
  // Biology XI scenes keep their original names (`<model>.js` for Chapter 1, `ch<N>_<model>.js` later); every other
  // book names its scenes with the book prefix, `c11-phy-ch<N>_<model>.js`, so one book never renders another's.
  const legacy = subject === "biology" && grade === "11";
  const sceneFiles = readdirSync(join(here, "scenes")).filter((f) => f.endsWith(".js") && (legacy ? !/^c\d+-/.test(f) : f.startsWith(PREFIX))).sort();
  for (const file of sceneFiles) {
    const name = file.replace(/\.js$/, "").replace(PREFIX, "");
    const m = name.match(/^ch(\d+)_(.+)$/);
    const chapter = m ? m[1] : "1";
    const id = `${PREFIX}ch${chapter}-m3d-${(m ? m[2] : name).replace(/_/g, "-")}`;
    const sceneSource = readFileSync(join(here, "scenes", file), "utf8");
    const page = await browser.newPage({ viewport: { width: POSTER.w, height: POSTER.h }, deviceScaleFactor: 1 });
    await page.route("https://figures.local/**", (route) => {
      const url = new URL(route.request().url());
      if (url.pathname === "/three.module.js") return route.fulfill({ body: threeSource, contentType: "text/javascript" });
      if (url.pathname === "/scene.js") return route.fulfill({ body: sceneSource.replace(/from "three"/g, 'from "./three.module.js"'), contentType: "text/javascript" });
      if (url.pathname === "/") return route.fulfill({ body: PAGE, contentType: "text/html" });
      return route.fulfill({ status: 404, body: "" });
    });
    page.on("pageerror", (e) => console.error("page error", name, e.message));
    await page.goto("https://figures.local/");
    await page.waitForFunction(() => window.__ready === true, null, { timeout: 60_000 });
    const title = await page.evaluate(() => window.__title);
    // Poster: labelled, large.
    await page.evaluate(([w, h]) => window.__render(w, h, 0, true), [POSTER.w, POSTER.h]);
    const poster = join(OUT, `${id}-poster.png`);
    await page.locator("#stage").screenshot({ path: poster, type: "png" });
    manifest.push({
      external_id: `${id}-poster`,
      kind: "image",
      title: `${title} (poster)`,
      file: `figures/${id}-poster.png`,
      provenance: { ...PROVENANCE, source: `Original three.js scene (scenes/${file}), labelled still`, tool: "three.js 0.170 rendered by headless Chromium (SwiftShader)" },
      bytes: statSync(poster).size,
    });
    // Turntable: FRAMES unlabelled stills of one full turn.
    await page.setViewportSize({ width: FRAME.w, height: FRAME.h });
    for (let i = 0; i < FRAMES; i++) {
      await page.evaluate(([w, h, angle]) => window.__render(w, h, angle, false), [FRAME.w, FRAME.h, (i / FRAMES) * Math.PI * 2]);
      const n = String(i + 1).padStart(2, "0");
      const out = join(OUT, `${id}-frame-${n}.png`);
      await page.locator("#stage").screenshot({ path: out, type: "png" });
      manifest.push({
        external_id: `${id}-frame-${n}`,
        kind: "image",
        title: `${title} (turn ${i + 1} of ${FRAMES})`,
        file: `figures/${id}-frame-${n}.png`,
        provenance: { ...PROVENANCE, source: `Original three.js scene (scenes/${file}), still ${i + 1} of ${FRAMES} of one full turn`, tool: "three.js 0.170 rendered by headless Chromium (SwiftShader)" },
        bytes: statSync(out).size,
      });
    }
    console.log("scene", id, "poster +", FRAMES, "frames");
    await page.close();
  }
}

await browser.close();
// A full run rewrites figures.json. A partial run (svg | scenes) merges: entries it regenerated replace their
// previous versions, everything else is kept, so the Chapter 1 turntables do not have to be re-rendered for a new SVG.
const manifestPath = join(OUT, "figures.json");
let items = manifest;
if (what !== "all" && existsSync(manifestPath)) {
  const fresh = new Set(manifest.map((m) => m.external_id));
  let kept = JSON.parse(readFileSync(manifestPath, "utf8")).items.filter((m) => !fresh.has(m.external_id));
  if (process.env.FIGURES_PRUNE) {
    // A vector diagram whose svg/ source was retired leaves the manifest and the figures folder.
    const retired = kept.filter((m) => /\(svg\/[^)]+\.svg\)$/.test(m.provenance?.source ?? "") && !existsSync(join(here, "svg", m.external_id + ".svg")));
    for (const m of retired) {
      const png = join(OUT, m.file.replace(/^figures\//, ""));
      if (existsSync(png)) unlinkSync(png);
      console.log("pruned", m.external_id);
    }
    const gone = new Set(retired.map((m) => m.external_id));
    kept = kept.filter((m) => !gone.has(m.external_id));
  }
  items = [...kept, ...manifest].sort((a, b) => a.external_id.localeCompare(b.external_id));
}
writeFileSync(manifestPath, JSON.stringify({ generated_by: "content/tools/figures/render.mjs", frames_per_turn: FRAMES, items }, null, 2) + "\n");
console.log("wrote figures.json with", items.length, "entries");
