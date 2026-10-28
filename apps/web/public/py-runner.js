// CODE-RUNNER-01: runs a lesson's Python program in the student's own browser (Pyodide, served from /pyodide/). A
// module worker, so a program that never ends can be stopped by ending the worker; nothing is sent to any server.
// Only the standard library is served, so a program that imports another package reports a ModuleNotFoundError.
//   in:  { code: string, stdin: string[] }
//   out: { type: "loading" } → { type: "started" } → { type: "done", output: string, error: string | null }
import { loadPyodide } from "/pyodide/pyodide.mjs";

let pyodide = null;

self.onmessage = async (event) => {
  const { code, stdin } = event.data;
  try {
    if (!pyodide) {
      self.postMessage({ type: "loading" });
      pyodide = await loadPyodide({ indexURL: "/pyodide/" });
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
