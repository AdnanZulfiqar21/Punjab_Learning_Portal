import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/api";

export type RequestState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: T };

type Settled<T> = { key: string } & ({ status: "error"; error: ApiError } | { status: "success"; data: T });

/**
 * Loads data with cancellation on unmount/argument change and an explicit retry (no silent infinite retries).
 * "loading" is derived: a result only counts if it belongs to the current request key.
 */
export function useRequest<T>(load: (signal: AbortSignal) => Promise<T>, deps: unknown[]) {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const key = JSON.stringify([...deps, attempt]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setSettled({ key, status: "success", data });
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        const error = e instanceof ApiError ? e : new ApiError("Something went wrong.", "server");
        setSettled({ key, status: "error", error });
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  let state: RequestState<T> = { status: "loading" };
  if (settled && settled.key === key) {
    state = settled.status === "success" ? { status: "success", data: settled.data } : { status: "error", error: settled.error };
  }
  return { state, retry };
}
