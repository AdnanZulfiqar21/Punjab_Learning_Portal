// P13.S3.T2 (OFFLINE-SYNC-01): lesson completions and note saves made offline wait here, each with an operation ID,
// filed under the account (ISOLATION-01), and are sent in order when the app is online again (on sign-in, when the
// app returns to the foreground, and right after something is queued). Replays are safe on the server: the same note
// text is "already saved" and a completion counts once. A note that changed on another device is not overwritten: the
// operation is dropped and the unsent text stays as the lesson's draft, where the learner chooses which to keep.
// Phones may stop apps in the background, so syncing is not promised while the app is closed.
import { Directory, File, Paths } from "expo-file-system";

import { accountScope } from "@/lib/account-scope";
import { api, ApiError } from "@/lib/api";

export type ProgressOp =
  | { op_id: string; kind: "completion"; lesson_id: string; done: boolean; queued_at: string }
  | { op_id: string; kind: "note"; lesson_id: string; text: string; base: number; queued_at: string };
export type NewProgressOp =
  | { kind: "completion"; lesson_id: string; done: boolean }
  | { kind: "note"; lesson_id: string; text: string; base: number };

const fileFor = (owner: string) => new File(Paths.document, `progress-queue-${accountScope(owner)}.json`);
const opId = () => Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");

export function pending(owner: string): ProgressOp[] {
  try {
    const f = fileFor(owner);
    return f.exists ? (JSON.parse(f.textSync()) as ProgressOp[]) : [];
  } catch {
    return [];
  }
}

function store(owner: string, ops: ProgressOp[]): void {
  const f = fileFor(owner);
  if (ops.length === 0) {
    if (f.exists) f.delete();
    return;
  }
  if (!f.exists) f.create();
  f.write(JSON.stringify(ops));
}

/** Queue a change; a newer change to the same lesson's completion or note replaces the older one. */
export function enqueue(owner: string, op: NewProgressOp): void {
  const ops = pending(owner).filter((o) => !(o.lesson_id === op.lesson_id && o.kind === op.kind));
  store(owner, [...ops, { ...op, op_id: opId(), queued_at: new Date().toISOString() } as ProgressOp]);
}

let running: Promise<number> | null = null;

/** Send what is queued, in order. Stops at the first offline failure; returns how many were sent. */
export function flush(token: string, owner: string): Promise<number> {
  running ??= (async () => {
    let sent = 0;
    try {
      for (const op of pending(owner)) {
        try {
          if (op.kind === "completion") await api.setCompleted(token, op.lesson_id, op.done);
          else await api.saveNote(token, op.lesson_id, op.text, op.base);
          sent += 1;
        } catch (e) {
          // Offline, a server problem or an ended session: stop and keep everything for later (the queue is this
          // account's). A conflict (the note changed elsewhere) or a lesson no longer readable: this operation can't
          // apply as it was, so it is dropped; the note's text stays in its draft for the learner to decide.
          if (e instanceof ApiError && ["offline", "server", "unauthorized"].includes(e.kind)) break;
        }
        store(owner, pending(owner).filter((o) => o.op_id !== op.op_id));
      }
    } finally {
      running = null;
    }
    return sent;
  })();
  return running;
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
