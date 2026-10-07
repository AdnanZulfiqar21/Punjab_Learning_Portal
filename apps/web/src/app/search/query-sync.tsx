"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";

/**
 * Fills the (static, never re-rendered) search form from the URL after hydration. The form itself is part of the
 * prerendered shell, so text typed before data arrives is never thrown away; a value the learner has already typed
 * is never overwritten.
 */
export function QuerySync({ formId }: { formId: string }) {
  const params = useSearchParams();
  useEffect(() => {
    const form = document.getElementById(formId) as HTMLFormElement | null;
    if (!form) return;
    const q = form.elements.namedItem("q") as HTMLInputElement | null;
    const grade = form.elements.namedItem("grade") as HTMLSelectElement | null;
    if (q && !q.value) q.value = params.get("q") ?? "";
    if (grade && !grade.value) grade.value = params.get("grade") ?? "";
  }, [formId, params]);
  return null;
}
