// CODE-RUNNER-01 (app): the page a hidden WebView loads to run a lesson's Python program on the device. Python is
// Pyodide 0.29.5, the same version the web portal serves itself, loaded here from the pinned jsDelivr path (the app has
// no web origin of its own yet); the WebView caches it after the first run. The program runs in a worker inside the
// page, so a program that never ends is stopped by ending that worker. Nothing is sent to any server of ours.
//   app → page: window.__run({ code, stdin })
//   page → app: { type: "loading" | "started" | "done" | "failed" | "timeout", output?, error? } as JSON

export const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/";
export const RUN_LIMIT_MS = 5000;

const WORKER = `
importScripts(${JSON.stringify(PYODIDE_URL)} + "pyodide.js");
let pyodide = null;
function tidy(message) {
  const lines = String(message).trimEnd().split("\\n");
  const first = lines.findIndex((l) => l.includes('File "<exec>"'));
  return (first > 0 ? ["Traceback (most recent call last):", ...lines.slice(first)] : lines).join("\\n");
}
onmessage = async (event) => {
  const { code, stdin } = event.data;
  try {
    if (!pyodide) {
      postMessage({ type: "loading" });
      pyodide = await loadPyodide({ indexURL: ${JSON.stringify(PYODIDE_URL)} });
    }
    let output = "";
    const answers = [...stdin];
    const decoder = new TextDecoder();
    pyodide.setStdout({ write: (b) => ((output += decoder.decode(b)), b.length) });
    pyodide.setStderr({ write: (b) => ((output += decoder.decode(b)), b.length) });
    pyodide.setStdin({ stdin: () => { const next = answers.shift(); if (next === undefined) return null; output += next + "\\n"; return next + "\\n"; }, autoEOF: true });
    postMessage({ type: "started" });
    const globals = pyodide.globals.get("dict")();
    try {
      pyodide.runPython(code, { globals });
      postMessage({ type: "done", output, error: null });
    } catch (err) {
      postMessage({ type: "done", output, error: tidy(err && err.message ? err.message : err) });
    } finally {
      globals.destroy();
    }
  } catch (err) {
    postMessage({ type: "failed", error: String(err && err.message ? err.message : err) });
  }
};
`;

export const RUNNER_PAGE = `<!doctype html><html><head><meta charset="utf-8"></head><body><script>
const WORKER = ${JSON.stringify(WORKER)};
let worker = null;
let timer = null;
function send(m) { window.ReactNativeWebView.postMessage(JSON.stringify(m)); }
function end() { if (worker) worker.terminate(); worker = null; }
window.__run = function (job) {
  if (!worker) {
    worker = new Worker(URL.createObjectURL(new Blob([WORKER], { type: "text/javascript" })));
    worker.onmessage = function (e) {
      const m = e.data;
      if (m.type === "started") timer = setTimeout(function () { end(); send({ type: "timeout" }); }, ${RUN_LIMIT_MS});
      if (m.type === "done" || m.type === "failed") clearTimeout(timer);
      if (m.type === "failed") end();
      send(m);
    };
    worker.onerror = function (e) { clearTimeout(timer); end(); send({ type: "failed", error: String((e && e.message) || "worker error") }); };
  }
  worker.postMessage(job);
};
</script></body></html>`;
