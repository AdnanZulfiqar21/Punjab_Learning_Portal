// Expo web target (development preview only): the queue lives in localStorage for this browser profile.
export type QueuedOp = { op_id: string; position: number; revision: number; option_id: string | null };
export type StoredQueue = { ops: QueuedOp[]; submitKey?: string };

const key = (attemptId: string) => `practice-queue:${attemptId}`;

export async function readQueue(attemptId: string): Promise<StoredQueue> {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key(attemptId)) ?? "") as StoredQueue;
    return { ops: Array.isArray(parsed.ops) ? parsed.ops : [], submitKey: parsed.submitKey };
  } catch {
    return { ops: [] };
  }
}

export async function writeQueue(attemptId: string, value: StoredQueue): Promise<void> {
  try {
    if (value.ops.length === 0 && !value.submitKey) window.localStorage.removeItem(key(attemptId));
    else window.localStorage.setItem(key(attemptId), JSON.stringify(value));
  } catch {
    /* storage unavailable */
  }
}
