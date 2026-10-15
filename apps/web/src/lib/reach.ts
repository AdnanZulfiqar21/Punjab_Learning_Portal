// A server action whose request never reaches the server (offline, a dropped connection) rejects instead of returning
// its result. Screens that show progress call actions through this, so a lost request becomes an ordinary failure and
// never a hang or an unhandled rejection (ANSWER-STATES-01, WRITTEN-CONNECTION-01).
export async function reach<T>(call: () => Promise<T>, failed: T): Promise<T> {
  try {
    return await call();
  } catch {
    return failed;
  }
}
