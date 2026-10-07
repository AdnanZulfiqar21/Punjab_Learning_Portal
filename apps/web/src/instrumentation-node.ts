// A deployed server with missing or development configuration exits non-zero (78, EX_CONFIG) with a clear message,
// so the platform sees a failed start instead of a process that is up but can never serve. Next.js would otherwise
// keep the process alive after a hook error.
import { readRuntimeConfig, WebConfigurationError } from "@/lib/runtime-config";

export function validateStartup(): void {
  try {
    const cfg = readRuntimeConfig();
    console.info(`[portal-web] role=${cfg.role} api=${cfg.apiOrigin}`);
  } catch (e) {
    if (e instanceof WebConfigurationError) {
      console.error(`[portal-web] ${e.message}`);
      process.exit(78);
    }
    throw e;
  }
}
