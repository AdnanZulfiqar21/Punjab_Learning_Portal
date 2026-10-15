// Expo web target (development preview only): the queue lives in localStorage for this browser profile.
import { accountScope } from "@/lib/account-scope";
import { api, ApiError } from "@/lib/api";
import { createFlusher, withOp, type NewProgressOp, type ProgressOp, type QueueStore } from "@/lib/progress-queue-core";

export type { NewProgressOp, ProgressOp };
const PREFIX = "progress-queue:";
const key = (owner: string) => `${PREFIX}${accountScope(owner)}`;
const opId = () => Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");

function storeFor(owner: string): QueueStore {
  return {
    read: () => {
      try {
        return JSON.parse(window.localStorage.getItem(key(owner)) ?? "[]") as ProgressOp[];
      } catch {
        return [];
      }
    },
    write: (ops) => {
      try {
        if (ops.length === 0) window.localStorage.removeItem(key(owner));
        else window.localStorage.setItem(key(owner), JSON.stringify(ops));
      } catch {
        /* storage unavailable */
      }
    },
  };
}

export function pending(owner: string): ProgressOp[] {
  return storeFor(owner).read();
}

export function enqueue(owner: string, op: NewProgressOp): void {
  const store = storeFor(owner);
  store.write(withOp(store.read(), op, opId(), new Date()));
}

const temporary = (e: unknown) => e instanceof ApiError && ["offline", "server", "unauthorized"].includes(e.kind);
const flights = new Map<string, Promise<number>>();

export function flush(token: string, owner: string): Promise<number> {
  const running = flights.get(owner);
  if (running) return running;
  const send = (op: ProgressOp) =>
    op.kind === "completion" ? api.setCompleted(token, op.lesson_id, op.done, op.queued_at).then(() => undefined) : api.saveNote(token, op.lesson_id, op.text, op.base).then(() => undefined);
  const flight = createFlusher(storeFor(owner), send, temporary)().finally(() => flights.delete(owner));
  flights.set(owner, flight);
  return flight;
}

export async function clearProgress(): Promise<void> {
  try {
    for (const k of Object.keys(window.localStorage)) if (k.startsWith(PREFIX)) window.localStorage.removeItem(k);
  } catch {
    /* storage unavailable */
  }
}
