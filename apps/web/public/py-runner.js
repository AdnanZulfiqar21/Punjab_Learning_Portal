// CODE-RUNNER-01: runs a lesson's Python program in the student's own browser (Pyodide, served from /pyodide/). A
// module worker, so a program that never ends can be stopped by ending the worker; nothing is sent to any server.
// Only the standard library is served, so a program that imports another package reports a ModuleNotFoundError.
//   in:  { code: string, stdin: string[] }
//   out: { type: "loading" } → { type: "started" } → { type: "done", output: string, error: string | null }
// SECURITY-HARDEN-01: once Python has loaded, the worker loses every way to make a request (fetch, XMLHttpRequest,
// WebSocket, EventSource, the Cache API, nested workers) and Python loses its bridge to JavaScript (`js`,
// `pyodide_js`, `pyodide.ffi`/`http`/`code`). A program can then only compute and print: it can never act as the
// signed-in reader against the portal, even if a lesson listing were written to try.
import { loadPyodide } from "/pyodide/pyodide.mjs";

let pyodide = null;

const NETWORK = ["fetch", "XMLHttpRequest", "WebSocket", "WebTransport", "EventSource", "caches", "importScripts", "Worker", "SharedWorker", "BroadcastChannel"];

/** Removes the request APIs from the worker (own properties and the prototype chain); returns any still reachable. */
function cutNetwork() {
  for (const name of NETWORK) {
    for (let o = self; o; o = Object.getPrototypeOf(o)) {
      if (Object.prototype.hasOwnProperty.call(o, name)) {
        try {
          delete o[name];
        } catch {
          /* checked below */
        }
        if (Object.prototype.hasOwnProperty.call(o, name)) {
          try {
            Object.defineProperty(o, name, { value: undefined, writable: false, configurable: false });
          } catch {
            /* checked below */
          }
        }
      }
    }
  }
  return NETWORK.filter((name) => self[name] !== undefined);
}

const NO_BRIDGE = `
import sys
class _LessonRunnerImports:
    BLOCKED = {"js", "pyodide_js", "pyodide.ffi", "pyodide.http", "pyodide.code", "pyodide.webloop", "micropip"}
    def find_spec(self, name, path=None, target=None):
        if name in self.BLOCKED or any(name.startswith(b + ".") for b in self.BLOCKED):
            raise ImportError(f"No module named '{name}' in the lesson runner")
        return None
for _name in [m for m in sys.modules if m in _LessonRunnerImports.BLOCKED]:
    del sys.modules[_name]
sys.meta_path.insert(0, _LessonRunnerImports())
del _LessonRunnerImports, sys
`;

self.onmessage = async (event) => {
  const { code, stdin } = event.data;
  try {
    if (!pyodide) {
      self.postMessage({ type: "loading" });
      const loaded = await loadPyodide({ indexURL: "/pyodide/" });
      loaded.runPython(NO_BRIDGE);
      const left = cutNetwork();
      if (left.length) throw new Error(`The code runner could not be made safe (${left.join(", ")}).`);
      pyodide = loaded;
    }
    let output = "";
    const answers = [...stdin];
    pyodide.setStdout({ write: (bytes) => ((output += new TextDecoder().decode(bytes)), bytes.length) });
    pyodide.setStderr({ write: (bytes) => ((output += new TextDecoder().decode(bytes)), bytes.length) });
    // input(): the next answer the student typed, shown after its prompt as a terminal would.
    pyodide.setStdin({
      stdin: () => {
        const next = answers.shift();
        if (next === undefined) return null;
        output += `${next}\n`;
        return `${next}\n`;
      },
      autoEOF: true,
    });
    self.postMessage({ type: "started" });
    const globals = pyodide.globals.get("dict")();
    try {
      pyodide.runPython(code, { globals });
      self.postMessage({ type: "done", output, error: null });
    } catch (err) {
      self.postMessage({ type: "done", output, error: tidy(String(err && err.message ? err.message : err)) });
    } finally {
      globals.destroy();
    }
  } catch (err) {
    self.postMessage({ type: "failed", error: String(err && err.message ? err.message : err) });
  }
};

/** A Python traceback without Pyodide's own frames: from the program's first line ("<exec>") on. */
function tidy(message) {
  const lines = message.trimEnd().split("\n");
  const first = lines.findIndex((l) => l.includes('File "<exec>"'));
  return (first > 0 ? ["Traceback (most recent call last):", ...lines.slice(first)] : lines).join("\n");
}
