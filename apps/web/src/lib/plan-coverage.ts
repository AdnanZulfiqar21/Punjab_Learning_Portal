// P14.S1.T2 (ENTITLEMENT-SCOPE-01): what a learner's current plans cover, in words. Null when one of them covers
// everything (the platform or the free trial). Scopes are copied onto each grant, so this never changes afterwards.
import type { Access } from "@portal/contracts";

type Scope = { grades?: number[]; subjects?: string[]; exams?: string[] };

const subjectName = (code: string) => code.charAt(0).toUpperCase() + code.slice(1).replaceAll("_", " ");

export function coverage(entitlements: Access["entitlements"]): string | null {
  const parts: string[] = [];
  for (const e of entitlements) {
    const s = (e.scope ?? {}) as Scope;
    if (!s.grades?.length && !s.subjects?.length && !s.exams?.length) return null;
    for (const g of s.grades ?? []) for (const sub of s.subjects ?? []) parts.push(`Class ${g === 11 ? "XI" : "XII"} ${subjectName(sub)}`);
    for (const x of s.exams ?? []) parts.push(`${x} mocks`);
  }
  return [...new Set(parts)].join(", ") || null;
}
