// Server-only: the learner's plans, trial and written allowance. Decided on the server; never cached.
import type { Access } from "@portal/contracts";
import { api } from "@/lib/session";

export async function getAccess(token: string): Promise<Access | null> {
  const res = await api<Access>("/v1/me/access", { token });
  return res.ok ? res.data : null;
}

export const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "long" });
