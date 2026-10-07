// Durable local queue for unacknowledged answer operations (P10.S2.T2). Stored as a small JSON file in the app's
// private document directory (OS-sandboxed, survives app termination). Never shown to the learner as "saved".
import { File, Paths } from "expo-file-system";

export type QueuedOp = { op_id: string; position: number; revision: number; option_id: string | null };
export type StoredQueue = { ops: QueuedOp[]; submitKey?: string };

const fileFor = (attemptId: string) => new File(Paths.document, `practice-queue-${attemptId}.json`);

export async function readQueue(attemptId: string): Promise<StoredQueue> {
  try {
    const f = fileFor(attemptId);
    if (!f.exists) return { ops: [] };
    const parsed = JSON.parse(await f.text()) as StoredQueue;
    return { ops: Array.isArray(parsed.ops) ? parsed.ops : [], submitKey: parsed.submitKey };
  } catch {
    return { ops: [] };
  }
}

export async function writeQueue(attemptId: string, value: StoredQueue): Promise<void> {
  const f = fileFor(attemptId);
  try {
    if (value.ops.length === 0 && !value.submitKey) {
      if (f.exists) f.delete();
      return;
    }
    if (!f.exists) f.create();
    f.write(JSON.stringify(value));
  } catch {
    /* storage failure: answers still go to the server immediately and are never shown as saved until acknowledged */
  }
}
