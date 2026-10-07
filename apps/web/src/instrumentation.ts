// Runs once when a Next.js server instance starts, before it serves requests. Node-only startup checks live in a
// separately imported module so the Edge bundle never contains Node APIs.
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { validateStartup } = await import("./instrumentation-node");
    validateStartup();
  }
}
