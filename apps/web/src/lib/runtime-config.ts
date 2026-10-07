// Runtime (not build-time) configuration for the web server (roadmap §5.5): one immutable build is promoted between
// environments and receives its environment-specific values from the process environment when it starts.

const DEPLOYED_ROLES = new Set(["staging", "production"]);
const DEV_MARKERS = ["localhost", "127.0.0.1", "[::1]"];

export interface WebRuntimeConfig {
  role: string;
  apiOrigin: string;
}

export class WebConfigurationError extends Error {
  constructor(message: string) {
    super(`Refusing to start the web server: ${message}`);
    this.name = "WebConfigurationError";
  }
}

export function readRuntimeConfig(env: Record<string, string | undefined> = process.env): WebRuntimeConfig {
  const role = env.PORTAL_ROLE ?? "development";
  const origin = env.PORTAL_API_INTERNAL_ORIGIN;
  if (DEPLOYED_ROLES.has(role)) {
    if (!origin) throw new WebConfigurationError(`PORTAL_API_INTERNAL_ORIGIN is required for role=${role}`);
    let url: URL;
    try {
      url = new URL(origin);
    } catch {
      throw new WebConfigurationError(`PORTAL_API_INTERNAL_ORIGIN is not a valid URL: ${origin}`);
    }
    if (role === "production" && DEV_MARKERS.some((m) => url.host.includes(m))) {
      throw new WebConfigurationError(`PORTAL_API_INTERNAL_ORIGIN points at a development host for role=production`);
    }
    return { role, apiOrigin: origin.replace(/\/$/, "") };
  }
  return { role, apiOrigin: (origin ?? "http://127.0.0.1:8100").replace(/\/$/, "") };
}
