export const STATUS_LABEL: Record<string, string> = {
  open: "Waiting for us",
  in_progress: "Being looked at",
  waiting_learner: "Waiting for your reply",
  resolved: "Resolved",
};

export const statusTone = (s: string) => (s === "waiting_learner" ? "warn" : s === "resolved" ? "ok" : "info") as "warn" | "ok" | "info";

export const CATEGORY_LABEL: Record<string, string> = {
  account: "Account",
  access: "Plan or trial",
  technical: "Technical",
  academic_report: "Question report",
  other: "Other",
};
