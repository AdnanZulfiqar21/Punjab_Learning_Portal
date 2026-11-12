// Runtime (not build-time) configuration for the web server (roadmap §5.5): one immutable build is promoted between
// environments and receives its environment-specific values from the process environment when it starts.

const DEPLOYED_ROLES = new Set(["staging", "production"]);
const DEV_MARKERS = ["localhost", "127.0.0.1", "[::1]"];

export interface WebRuntimeConfig {
  role: string;
  apiOrigin: string;
  /** P11.S1.T1: the site's public origin (for the sitemap). Optional; without it no sitemap is advertised. */
  publicOrigin?: string;
}

function publicOrigin(env: Record<string, string | undefined>): string | undefined {
  const v = env.PORTAL_PUBLIC_ORIGIN;
  if (!v) return undefined;
  try {
    const u = new URL(v);
    return u.protocol === "https:" || u.protocol === "http:" ? u.origin : undefined;
  } catch {
    throw new WebConfigurationError(`PORTAL_PUBLIC_ORIGIN is not a valid URL: ${v}`);
  }
}

export class WebConfigurationError extends Error {
  constructor(message: string) {
    super(`Refusing to start the web server: ${message}`);
    this.name = "WebConfigurationError";
  }
}

const ROLES = new Set(["development", "test", "staging", "production"]);

/** ROLE-EXPLICIT-01 (security audit 2026-11, H1): a production build (`next start`) must be told its role. Without
 * one it would run as "development": session cookies without `Secure` and no check of the API address, with no
 * error to notice. A local run of the production build says so: `PORTAL_ROLE=development`. The build step itself
 * needs no role. */
export function requireExplicitRole(env: Record<string, string | undefined>): void {
  if (env.NODE_ENV !== "production" || env.NEXT_PHASE === "phase-production-build") return;
  const role = env.PORTAL_ROLE;
  if (!role) {
    throw new WebConfigurationError(
      "PORTAL_ROLE is required for a production build (production or staging on a server; development for a local run)",
    );
  }
  if (!ROLES.has(role)) throw new WebConfigurationError(`PORTAL_ROLE is not a known role: ${role}`);
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
    return { role, apiOrigin: origin.replace(/\/$/, ""), publicOrigin: publicOrigin(env) };
  }
  return { role, apiOrigin: (origin ?? "http://127.0.0.1:8100").replace(/\/$/, ""), publicOrigin: publicOrigin(env) };
}
