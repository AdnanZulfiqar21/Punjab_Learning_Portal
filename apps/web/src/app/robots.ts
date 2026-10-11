import type { MetadataRoute } from "next";
import { connection } from "next/server";
import { robotsRules } from "@/lib/robots-rules";
import { readRuntimeConfig } from "@/lib/runtime-config";

// P11.S1.T1 (PUBLIC-SITE-01): computed per request from the runtime role, never baked into the build, because one
// build is promoted from staging to production (§5.5).
export default async function robots(): Promise<MetadataRoute.Robots> {
  await connection();
  const { role, publicOrigin } = readRuntimeConfig();
  return robotsRules(role, publicOrigin);
}
