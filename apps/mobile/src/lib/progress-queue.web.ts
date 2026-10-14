// Expo web target (development preview only): the queue lives in localStorage for this browser profile.
import { accountScope } from "@/lib/account-scope";
import { api, ApiError } from "@/lib/api";
import type { NewProgressOp, ProgressOp } from "./progress-queue";

export type { NewProgressOp, ProgressOp };
const PREFIX = "progress-queue:";
const key = (owner: string) => `${PREFIX}${accountScope(owner)}`;
const opId = () => Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");

export function pending(owner: string): ProgressOp[] {
  try {
    return JSON.parse(window.localStorage.getItem(key(owner)) ?? "[]") as ProgressOp[];
  } catch {
    return [];
  }
}

function store(owner: string, ops: ProgressOp[]): void {
  try {
    if (ops.length === 0) window.localStorage.removeItem(key(owner));
    else window.localStorage.setItem(key(owner), JSON.stringify(ops));
  } catch {
    /* storage unavailable */
  }
}

export function enqueue(owner: string, op: NewProgressOp): void {
  const ops = pending(owner).filter((o) => !(o.lesson_id === op.lesson_id && o.kind === op.kind));
  store(owner, [...ops, { ...op, op_id: opId(), queued_at: new Date().toISOString() } as ProgressOp]);
}

export async function flush(token: string, owner: string): Promise<number> {
  let sent = 0;
  for (const op of pending(owner)) {
    try {
      if (op.kind === "completion") await api.setCompleted(token, op.lesson_id, op.done, op.queued_at);
      else await api.saveNote(token, op.lesson_id, op.text, op.base);
      sent += 1;
    } catch (e) {
      if (e instanceof ApiError && ["offline", "server", "unauthorized"].includes(e.kind)) break;
    }
    store(owner, pending(owner).filter((o) => o.op_id !== op.op_id));
  }
  return sent;
}

export async function clearProgress(): Promise<void> {
  try {
    for (const k of Object.keys(window.localStorage)) if (k.startsWith(PREFIX)) window.localStorage.removeItem(k);
  } catch {
    /* storage unavailable */
  }
}
