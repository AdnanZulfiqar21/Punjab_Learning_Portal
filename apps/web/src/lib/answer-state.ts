// The five answer states of roadmap §6.1 (P10.S2, P13.S2.T2; ANSWER-STATES-01). An unacknowledged change is "selected"
// while it is only on this device and not yet sent, "saving" while a request carries it, and "pending" once a send
// failed, the connection is down, the change was restored from an earlier session or another device holds the test.
// Only the server's receipt makes it "saved"; "selected" is never shown as saved. Kept identical on web and mobile.
export type ItemStatus = "saved" | "pending" | "rejected" | "empty";
export type AnswerState = "empty" | "selected" | "saving" | "saved" | "pending" | "rejected";

export function answerState(status: ItemStatus, { sending, held }: { sending: boolean; held: boolean }): AnswerState {
  if (status !== "pending") return status;
  if (sending) return "saving";
  return held ? "pending" : "selected";
}

/** How a question's state is read out in the question palette. */
export const PALETTE_LABEL: Record<AnswerState, string> = {
  empty: "not answered",
  selected: "selected, not sent yet",
  saving: "saving",
  saved: "saved",
  pending: "not saved yet, kept on this device",
  rejected: "not saved",
};

/** The line under the options for the current question ("" when there is nothing to say). */
export function stateLine(state: AnswerState, { elsewhere, reason }: { elsewhere: boolean; reason?: string }): string {
  switch (state) {
    case "selected":
      return "Selected · not sent yet";
    case "saving":
      return "Saving…";
    case "saved":
      return "Saved";
    case "pending":
      return elsewhere
        ? "Not saved: kept on this device until you continue here"
        : "Not saved yet: kept on this device and sent again when the connection is back";
    case "rejected":
      return `Not saved: ${reason ?? "the server refused it."}`;
    default:
      return "";
  }
}
