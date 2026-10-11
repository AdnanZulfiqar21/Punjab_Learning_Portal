// Expo web target (development preview only): the queue lives in localStorage for this browser profile.
export type QueuedOp = { op_id: string; position: number; revision: number; option_id: string | null };
export type StoredQueue = { ops: QueuedOp[]; submitKey?: string };

const PREFIX = "practice-queue:";
const key = (attemptId: string) => `${PREFIX}${attemptId}`;

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

export async function clearQueues(): Promise<void> {
  try {
    for (const k of Object.keys(window.localStorage)) if (k.startsWith(PREFIX)) window.localStorage.removeItem(k);
  } catch {
    /* storage unavailable */
  }
}
