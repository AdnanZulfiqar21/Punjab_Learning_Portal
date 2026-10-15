// P13.S3.T2 (OFFLINE-SYNC-01; OFFLINE-CORE-01): the offline progress queue's rules, with storage and sending injected
// so they run on the host in tests. `progress-queue.ts` (native files) and `progress-queue.web.ts` (localStorage) bind
// them; neither repeats the rules.
export type ProgressOp =
  | { op_id: string; kind: "completion"; lesson_id: string; done: boolean; queued_at: string }
  | { op_id: string; kind: "note"; lesson_id: string; text: string; base: number; queued_at: string };
export type NewProgressOp =
  | { kind: "completion"; lesson_id: string; done: boolean }
  | { kind: "note"; lesson_id: string; text: string; base: number };

export type QueueStore = {
  read(): ProgressOp[]; // what is waiting, oldest first ([] when nothing or unreadable)
  write(ops: ProgressOp[]): void; // replace it ([] removes it)
};

/** A newer change to the same lesson's completion or note replaces the older one; it goes to the back. */
export function withOp(ops: ProgressOp[], op: NewProgressOp, opId: string, now: Date): ProgressOp[] {
  const kept = ops.filter((o) => !(o.lesson_id === op.lesson_id && o.kind === op.kind));
  return [...kept, { ...op, op_id: opId, queued_at: now.toISOString() } as ProgressOp];
}

/**
 * Send what is queued, in order, one flush at a time. An error `stop` says is temporary (offline, a server problem,
 * an ended session) stops the flush and keeps everything. Any other error (the note changed on another device, the
 * lesson is no longer readable) means that operation can't apply as it was: it is dropped and the rest go on. Each
 * operation leaves the queue only after it was sent or dropped, so a crash mid-flush resends at most that one, and
 * replays are safe on the server. Returns how many were sent.
 */
export function createFlusher(
  store: QueueStore,
  send: (op: ProgressOp) => Promise<void>,
  stop: (e: unknown) => boolean,
): () => Promise<number> {
  let running: Promise<number> | null = null;
  return () => {
    running ??= (async () => {
      let sent = 0;
      try {
        for (const op of store.read()) {
          try {
            await send(op);
            sent += 1;
          } catch (e) {
            if (stop(e)) break;
          }
          store.write(store.read().filter((o) => o.op_id !== op.op_id));
        }
      } finally {
        running = null;
      }
      return sent;
    })();
    return running;
  };
}
