// P13.S3.T2 (OFFLINE-SYNC-01): lesson completions and note saves made offline wait here, each with an operation ID,
// filed under the account (ISOLATION-01), and are sent in order when the app is online again (on sign-in, when the
// app returns to the foreground, and right after something is queued). Replays are safe on the server: the same note
// text is "already saved" and a completion counts once. A note that changed on another device is not overwritten: the
// operation is dropped and the unsent text stays as the lesson's draft, where the learner chooses which to keep.
// Phones may stop apps in the background, so syncing is not promised while the app is closed.
import { Directory, File, Paths } from "expo-file-system";

import { accountScope } from "@/lib/account-scope";
import { api, ApiError } from "@/lib/api";
import { createFlusher, withOp, type NewProgressOp, type ProgressOp, type QueueStore } from "@/lib/progress-queue-core";

export type { NewProgressOp, ProgressOp };

const fileFor = (owner: string) => new File(Paths.document, `progress-queue-${accountScope(owner)}.json`);
const opId = () => Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");

function storeFor(owner: string): QueueStore {
  return {
    read: () => {
      try {
        const f = fileFor(owner);
        return f.exists ? (JSON.parse(f.textSync()) as ProgressOp[]) : [];
      } catch {
        return [];
      }
    },
    write: (ops) => {
      const f = fileFor(owner);
      if (ops.length === 0) {
        if (f.exists) f.delete();
        return;
      }
      if (!f.exists) f.create();
      f.write(JSON.stringify(ops));
    },
  };
}

export function pending(owner: string): ProgressOp[] {
  return storeFor(owner).read();
}

/** Queue a change; a newer change to the same lesson's completion or note replaces the older one. */
export function enqueue(owner: string, op: NewProgressOp): void {
  const store = storeFor(owner);
  store.write(withOp(store.read(), op, opId(), new Date()));
}

const temporary = (e: unknown) => e instanceof ApiError && ["offline", "server", "unauthorized"].includes(e.kind);
const flights = new Map<string, Promise<number>>();

/** Send what is queued, in order. Stops at the first temporary failure; returns how many were sent. */
export function flush(token: string, owner: string): Promise<number> {
  const running = flights.get(owner);
  if (running) return running;
  const send = (op: ProgressOp) =>
    op.kind === "completion" ? api.setCompleted(token, op.lesson_id, op.done, op.queued_at).then(() => undefined) : api.saveNote(token, op.lesson_id, op.text, op.base).then(() => undefined);
  const flight = createFlusher(storeFor(owner), send, temporary)().finally(() => flights.delete(owner));
  flights.set(owner, flight);
  return flight;
}

/** Signing out of this device: every account's queue goes with the session (ISOLATION-01). */
export async function clearProgress(): Promise<void> {
  try {
    for (const entry of new Directory(Paths.document).list()) {
      if (entry instanceof File && entry.name.startsWith("progress-queue-")) entry.delete();
    }
  } catch {
    /* nothing readable to clear */
  }
}
