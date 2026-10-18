// Mobile API client. The API origin is variant configuration (app.config.ts → extra.apiOrigin); grading, entitlements
// and authorisation stay on the server (roadmap §5.3). Authenticated calls send the app session token as a bearer.
import Constants from "expo-constants";
import { Platform } from "react-native";
import type {
  Access,
  AppSession,
  MockReadiness,
  MockSession,
  NotebookEntry,
  ProgressReport,
  Dashboard,
  ReadingPosition,
  StudyNote,
  StudyNoteListed,
  FavouriteTopic,
  SavedFormula,
  EvidenceReport,
  StudyPlan,
  PublishedExamProfile,
  AssistedAccess,
  AttemptResult,
  Book,
  Catalogue,
  Chapter,
  Discovery,
  Lesson,
  Me,
  StudySettings,
  StudySettingsPatch,
  PracticeAttempt,
  PracticeAvailability,
  PracticeForm,
  Problem,
  ProfileInput,
  RevealResult,
  RuntimeConfig,
  SaveResult,
  SearchResult,
  SessionCreated,
  SubmitResult,
  TopicLecture,
  HelpArticle,
  HelpArticleSummary,
  Inbox,
  SupportTicket,
  TrialDecision,
  ClientPolicy,
  StudyPack,
  StudyPackStatus,
  TrialDevice,
  LinkedForm,
  WrittenAttempt,
  WrittenPage,
  WrittenAvailability,
  WrittenForm,
  WrittenResult,
  WrittenSeal,
} from "@portal/contracts";

import { discoveryPath, type DiscoveryFilters } from "@/lib/discovery";
import { installToken } from "@/lib/install-token";

function deviceName(): string {
  return Platform.OS === "ios" ? "iPhone or iPad" : Platform.OS === "android" ? "Android device" : "Web browser";
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly kind: "offline" | "not_found" | "server" | "unauthorized" | "invalid" | "conflict",
    readonly correlationId?: string | null,
    readonly problem?: Problem | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type { TopicLecture };

export type TopicReading = {
  topic_id: string;
  number: string | null;
  title: string;
  chapter_id: string;
  chapter_number: number;
  chapter_title: string;
  grade_number: number;
  subject_name: string;
  availability: "published" | "private_preview" | "unavailable";
  lesson: (Lesson & { status: string; private_preview: boolean }) | null;
  previous_topic_id: string | null;
  next_topic_id: string | null;
};

function origin(): string {
  const value = Constants.expoConfig?.extra?.apiOrigin;
  if (typeof value !== "string" || !value) throw new ApiError("App configuration is missing the API address.", "server");
  return value;
}

/** A diagram from a question in the learner's own attempt (QUESTION-DIAGRAMS-01). */
export function attemptAsset(attemptId: string, versionId: string, token: string): { uri: string; headers: Record<string, string> } {
  return {
    uri: `${origin()}/v1/attempts/${encodeURIComponent(attemptId)}/assets/${encodeURIComponent(versionId)}`,
    headers: { Authorization: `Bearer ${token}` },
  };
}

/** A lesson's diagram or handout (P07.S1.T1): only files named by its published version, under its access tier. */
/** P13.S3.T1: an absolute API URL for a path the server returned (e.g. a study pack's file list). */
export function apiUrl(path: string): string {
  return `${origin()}${path}`;
}

/** W03.S1.T3 (MOBILE-TRANSFORMS-01): your own page's preview, as currently turned and enhanced (never the original). */
export function writtenPageImage(
  attemptId: string,
  page: { id: string; transform?: unknown },
  token: string,
): { uri: string; headers: Record<string, string> } {
  const v = encodeURIComponent(JSON.stringify(page.transform ?? {})); // a new transform is a new image, never a stale cache
  return {
    uri: `${origin()}/v1/written-attempts/${encodeURIComponent(attemptId)}/pages/${encodeURIComponent(page.id)}?v=${v}`,
    headers: { Authorization: `Bearer ${token}` },
  };
}

export function previewAsset(topicId: string, versionId: string, token: string): { uri: string; headers: Record<string, string> } {
  return {
    uri: `${origin()}/v1/topics/${encodeURIComponent(topicId)}/preview-assets/${encodeURIComponent(versionId)}`,
    headers: { Authorization: `Bearer ${token}` },
  };
}

export function lessonAsset(lessonId: string, versionId: string, token: string | null): { uri: string; headers?: Record<string, string> } {
  const uri = `${origin()}/v1/lessons/${encodeURIComponent(lessonId)}/assets/${encodeURIComponent(versionId)}`;
  return token ? { uri, headers: { Authorization: `Bearer ${token}` } } : { uri };
}

function correlationId(): string {
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  /** A raw upload body (a photo or PDF); sent as application/octet-stream. */
  raw?: Blob;
  cache?: "no-store";
};

// Every request says which client it is and carries this installation's opaque token, so the server can apply the
// trial device rules (roadmap §16.4). Until request attestation exists (B07) these are asserted by the app.
export const CLIENT = Platform.OS === "web" ? "web" : "native";
export const SURFACE: "web" | "ios" | "android" = Platform.OS === "ios" ? "ios" : Platform.OS === "android" ? "android" : "web";
export const APP_VERSION: string | null = Constants.expoConfig?.version ?? null;

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const cid = correlationId();
  const install = await installToken();
  let res: Response;
  try {
    res = await fetch(`${origin()}${path}`, {
      method: opts.method ?? "GET",
      headers: {
        Accept: "application/json",
        "X-Correlation-ID": cid,
        "X-Portal-Client": CLIENT,
        "X-Portal-Platform": SURFACE, // P13.S1.T4: which build is asking, so an unsupported one is told to update
        ...(APP_VERSION ? { "X-Portal-App-Version": APP_VERSION } : {}),
        "X-Portal-Install": install,
        ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(opts.raw !== undefined ? { "Content-Type": "application/octet-stream" } : {}),
        ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
        ...opts.headers,
      },
      body: opts.raw ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
      cache: opts.cache,
      signal: opts.signal ?? AbortSignal.timeout(opts.raw !== undefined ? 120_000 : 15_000),
    });
  } catch (e) {
    if ((e as Error).name === "AbortError" && opts.signal?.aborted) throw e;
    throw new ApiError("Can't reach the learning service. Check your connection and try again.", "offline", cid);
  }
  if (res.status === 204) return undefined as T;
  if (res.ok) return (await res.json()) as T;
  const problem = (await res.json().catch(() => null)) as Problem | null;
  const ref = problem?.correlation_id ?? cid;
  const detail = problem?.detail;
  if (res.status === 404 || res.status === 410) throw new ApiError(detail ?? "Not found.", "not_found", ref, problem);
  if (res.status === 401) throw new ApiError(detail ?? "Please sign in again.", "unauthorized", ref, problem);
  if (res.status === 426) throw new ApiError(detail ?? "Please update the app to continue.", "server", ref, problem);
  if (res.status === 422) throw new ApiError(detail ?? "Please check your entries.", "invalid", ref, problem);
  if (res.status === 409) throw new ApiError(detail ?? "This changed elsewhere.", "conflict", ref, problem);
  throw new ApiError(detail ?? `Service error (${res.status}).`, "server", ref, problem);
}

function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal });
}

export const api = {
  catalogue: (signal?: AbortSignal) => getJSON<Catalogue>("/v1/catalogue", signal),
  /** P13.S2.T1: published lessons, previews and practice per book. Class XI and XII stay separate. */
  discovery: (filters: DiscoveryFilters, signal?: AbortSignal) => getJSON<Discovery>(discoveryPath(filters), signal),
  bookFor: (grade: number, subject: string, signal?: AbortSignal) =>
    getJSON<Book>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/book`, signal),
  chapter: (id: string, signal?: AbortSignal) => getJSON<Chapter>(`/v1/chapters/${encodeURIComponent(id)}`, signal),
  /** P11.S2.T3 (SEARCH-01): chapters, topics and published lessons. With a session, lesson text the learner's plan
   * covers can match too; otherwise lessons match by title only and come back locked. */
  search: (q: string, grade: number | undefined, token: string | null, signal?: AbortSignal) => {
    const params = new URLSearchParams({ q, lessons: "true" });
    if (grade) params.set("grade", String(grade));
    return request<SearchResult>(`/v1/search?${params.toString()}`, { token, signal });
  },
  runtimeConfig: (signal?: AbortSignal) => getJSON<RuntimeConfig>("/v1/runtime-config", signal),
  /** Published, live lessons only (independently reviewed); drafts never reach the app. */
  // Premium bodies come back only with a session that has an active plan or trial (review R07).
  topicLesson: (topicId: string, token: string | null, signal?: AbortSignal, language?: string) =>
    request<TopicReading>(
      `/v1/topics/${encodeURIComponent(topicId)}/lesson${language && language !== "en" ? `?language=${encodeURIComponent(language)}` : ""}`,
      { token, signal, cache: "no-store", headers: { "Cache-Control": "no-cache" } },
    ),
  /** LECTURE-READ-01: the topic's approved lecture (locked without a plan or trial), or that it is coming. */
  topicLecture: (topicId: string, token: string | null, signal?: AbortSignal) =>
    request<TopicLecture>(`/v1/topics/${encodeURIComponent(topicId)}/lecture`, { token, signal, cache: "no-store" }),
  lessons: (chapterId: string, token: string | null, signal?: AbortSignal, language?: string) =>
    request<Lesson[]>(
      `/v1/chapters/${encodeURIComponent(chapterId)}/lessons${language && language !== "en" ? `?language=${encodeURIComponent(language)}` : ""}`,
      { token, signal },
    ),

  // Development identity adapter: the API exposes it only in development/test and keeps it out of the contract.
  devRegister: (email: string, password: string) =>
    request<void>("/v1/dev-auth/register", { method: "POST", body: { email, password } }),
  devToken: (email: string, password: string) =>
    request<{ access_token: string }>("/v1/dev-auth/token", { method: "POST", body: { email, password } }),

  // App sessions (IMPL-12) are created only from a verified IdP access token.
  createSession: (idpToken: string, deviceLabel: string) =>
    request<SessionCreated>("/v1/sessions", {
      method: "POST",
      token: idpToken,
      body: { kind: "native", device_label: deviceLabel },
    }),
  me: (token: string, signal?: AbortSignal) => request<Me>("/v1/me", { token, signal }),
  // P04.S3.T2 (SETTINGS-01): the account's usual study settings; only the settings given change.
  settings: (token: string, signal?: AbortSignal) => request<StudySettings>("/v1/me/settings", { token, signal }),
  saveSettings: (token: string, patch: StudySettingsPatch) =>
    request<StudySettings>("/v1/me/settings", { method: "PATCH", token, body: patch }),
  sessions: (token: string, signal?: AbortSignal) => request<AppSession[]>("/v1/me/sessions", { token, signal }),
  revokeSession: (token: string, id: string) =>
    request<void>(`/v1/me/sessions/${encodeURIComponent(id)}`, { method: "DELETE", token }),
  revokeOthers: (token: string) => request<void>("/v1/me/sessions/revoke-others", { method: "POST", token }),
  // P15.S3.T3 / P18.S3.T2: support's assisted access to my activity, and account deletion requests.
  assistedAccess: (token: string, signal?: AbortSignal) => request<AssistedAccess[]>("/v1/me/assisted-access", { token, signal }),
  endAssistedAccess: (token: string, id: string) =>
    request<void>(`/v1/me/assisted-access/${encodeURIComponent(id)}`, { method: "DELETE", token }),
  requestDeletion: (token: string, confirmEmail: string, reason: string | null) =>
    request<{ ticket_id: string }>("/v1/me/deletion-request", { method: "POST", token, body: { confirm_email: confirmEmail, reason } }),
  signOut: (token: string) => request<void>("/v1/me/session", { method: "DELETE", token }),
  saveProfile: (token: string, body: ProfileInput) => request<unknown>("/v1/me/profile", { method: "PUT", token, body }),

  // Plans (P14): trial status, entitlements and the written allowance; the trial is one-time and idempotent.
  access: (token: string, signal?: AbortSignal) => request<Access>("/v1/me/access", { token, signal }),
  // Trial activation is a durable, idempotent claim (roadmap §16.4): retries with the same key recover the same claim.
  claimTrial: async (token: string) =>
    request<TrialDecision>("/v1/me/trial/claims", {
      method: "POST",
      token,
      body: { surface: SURFACE, idempotency_key: `trial-${(await installToken()).slice(0, 40)}`, proof: {}, label: deviceName() },
    }),
  authorizeDevice: (token: string) =>
    request<TrialDecision>("/v1/me/trial/devices", { method: "POST", token, body: { surface: SURFACE, proof: {}, label: deviceName() } }),
  trialDevices: (token: string, signal?: AbortSignal) => request<TrialDevice[]>("/v1/me/trial/devices", { token, signal }),
  clientPolicy: (platform: string, version: string) =>
    getJSON<ClientPolicy>(`/v1/clients/policy?platform=${encodeURIComponent(platform)}&version=${encodeURIComponent(version)}`),
  studyPack: (token: string, chapterId: string, format: number) =>
    request<StudyPack>(`/v1/me/study-packs/${encodeURIComponent(chapterId)}?format=${format}`, { token, signal: AbortSignal.timeout(60_000) }),
  studyPackStatus: (token: string, chapterId: string) =>
    request<StudyPackStatus>(`/v1/me/study-packs/${encodeURIComponent(chapterId)}/status`, { token }),
  removeTrialDevice: (token: string, id: string) =>
    request<void>(`/v1/me/trial/devices/${encodeURIComponent(id)}`, { method: "DELETE", token }),

  // Practice (P09/P10). Attempt payloads never contain keys; results release them after submission.
  practiceAvailability: (token: string, grade: number, subject: string, signal?: AbortSignal) =>
    request<PracticeAvailability>(`/v1/practice/availability?grade=${grade}&subject=${encodeURIComponent(subject)}`, {
      token,
      signal,
    }),
  createPracticeForm: (token: string, idempotencyKey: string, body: Record<string, unknown>) =>
    request<PracticeForm>("/v1/practice/forms", { method: "POST", token, body, headers: { "Idempotency-Key": idempotencyKey } }),
  // P09.S2/P12: mocks, scheduled sessions, the mistake notebook and the progress report.
  examProfiles: (token: string, signal?: AbortSignal) => request<PublishedExamProfile[]>("/v1/exam-profiles", { token, signal }),
  mockReadiness: (token: string, code: string, signal?: AbortSignal) =>
    request<MockReadiness>(`/v1/mocks/${encodeURIComponent(code)}/readiness`, { token, signal }),
  createMock: (token: string, idempotencyKey: string, code: string) =>
    request<PracticeForm>("/v1/mocks", { method: "POST", token, body: { code }, headers: { "Idempotency-Key": idempotencyKey } }),
  mockSessions: (token: string, signal?: AbortSignal) => request<MockSession[]>("/v1/mock-sessions", { token, signal }),
  joinSession: (token: string, id: string) =>
    request<{ attempt_id: string }>(`/v1/mock-sessions/${encodeURIComponent(id)}/join`, { method: "POST", token }),
  notebook: (token: string, signal?: AbortSignal) => request<NotebookEntry[]>("/v1/me/notebook", { token, signal }),
  reviewTest: (token: string, idempotencyKey: string, grade: number, subject: string) =>
    request<PracticeForm>("/v1/me/notebook/review", {
      method: "POST",
      token,
      body: { grade, subject, count: 10 },
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  progress: (token: string, signal?: AbortSignal) => request<ProgressReport>("/v1/me/progress", { token, signal }),
  dashboard: (token: string, signal?: AbortSignal) => request<Dashboard>("/v1/me/dashboard", { token, signal }),
  /** ROLLOUT-01: which rolled-out features this account has (a flag only ever hides things). */
  features: (token: string, signal?: AbortSignal) => request<Record<string, boolean>>("/v1/me/features", { token, signal }),
  // LESSON-DONE-01 and STUDY-TOOLS-01: completion, private notes, favourite topics and saved formulas.
  completedLessons: (token: string, chapterId: string, signal?: AbortSignal) =>
    request<string[]>(`/v1/me/chapters/${encodeURIComponent(chapterId)}/completed-lessons`, { token, signal }),
  // LESSON-PROGRESS-01: a queued (offline) change carries when the learner acted, so a late one never reverses a newer one.
  setCompleted: (token: string, lessonId: string, done: boolean, clientAt?: string) =>
    request<void>(
      `/v1/me/lessons/${encodeURIComponent(lessonId)}/complete${clientAt ? `?client_at=${encodeURIComponent(clientAt)}` : ""}`,
      { method: done ? "POST" : "DELETE", token },
    ),
  readingPosition: (token: string, chapterId: string, signal?: AbortSignal) =>
    request<ReadingPosition | null>(`/v1/me/chapters/${encodeURIComponent(chapterId)}/reading-position`, { token, signal }),
  saveReadingPosition: (token: string, lessonId: string) =>
    request<ReadingPosition>("/v1/me/reading-position", { method: "PUT", token, body: { lesson_id: lessonId, block_index: 0 } }),
  note: (token: string, lessonId: string, signal?: AbortSignal) =>
    request<StudyNote>(`/v1/me/lessons/${encodeURIComponent(lessonId)}/note`, { token, signal }),
  saveNote: (token: string, lessonId: string, text: string, baseRevision: number) =>
    request<StudyNote>(`/v1/me/lessons/${encodeURIComponent(lessonId)}/note`, { method: "PUT", token, body: { text, base_revision: baseRevision } }),
  deleteNote: (token: string, lessonId: string, baseRevision: number) =>
    request<StudyNote>(`/v1/me/lessons/${encodeURIComponent(lessonId)}/note?base_revision=${baseRevision}`, { method: "DELETE", token }),
  notes: (token: string, signal?: AbortSignal) => request<StudyNoteListed[]>("/v1/me/notes", { token, signal }),
  favourites: (token: string, signal?: AbortSignal) => request<FavouriteTopic[]>("/v1/me/favourites", { token, signal }),
  setFavourite: (token: string, topicId: string, on: boolean) =>
    request<void>(`/v1/me/favourites/topics/${encodeURIComponent(topicId)}`, { method: on ? "PUT" : "DELETE", token }),
  formulas: (token: string, signal?: AbortSignal) => request<SavedFormula[]>("/v1/me/formulas", { token, signal }),
  saveFormula: (token: string, lessonId: string, blockIndex: number) =>
    request<SavedFormula>("/v1/me/formulas", { method: "POST", token, body: { lesson_id: lessonId, block_index: blockIndex } }),
  removeFormula: (token: string, id: string) => request<void>(`/v1/me/formulas/${encodeURIComponent(id)}`, { method: "DELETE", token }),
  evidence: (token: string, grade: number, subject: string, signal?: AbortSignal) =>
    request<EvidenceReport>(`/v1/me/evidence?grade=${grade}&subject=${encodeURIComponent(subject)}`, { token, signal }),
  studyPlan: (token: string, q: { grade: number; subject: string; target_date: string; daily_minutes: number }, signal?: AbortSignal) =>
    request<StudyPlan>(
      `/v1/me/study-plan?grade=${q.grade}&subject=${encodeURIComponent(q.subject)}&target_date=${encodeURIComponent(q.target_date)}&daily_minutes=${q.daily_minutes}`,
      { token, signal },
    ),
  startAttempt: (token: string, formId: string) =>
    request<PracticeAttempt>(`/v1/practice/forms/${encodeURIComponent(formId)}/attempt`, { method: "POST", token }),
  attempt: (token: string, id: string, signal?: AbortSignal) =>
    request<PracticeAttempt>(`/v1/attempts/${encodeURIComponent(id)}`, { token, signal }),
  continueHere: (token: string, id: string) =>
    request<PracticeAttempt>(`/v1/attempts/${encodeURIComponent(id)}/continue-here`, { method: "POST", token }),
  setFlags: (token: string, id: string, positions: number[]) =>
    request<{ flagged: number[] }>(`/v1/attempts/${encodeURIComponent(id)}/flags`, { method: "PUT", token, body: { positions } }),
  saveAnswers: (token: string, id: string, ops: unknown[]) =>
    request<SaveResult>(`/v1/attempts/${encodeURIComponent(id)}/answers`, { method: "POST", token, body: { ops } }),
  submitAttempt: (token: string, id: string, idempotencyKey: string, ops: unknown[]) =>
    request<SubmitResult>(`/v1/attempts/${encodeURIComponent(id)}/submit`, {
      method: "POST",
      token,
      body: { idempotency_key: idempotencyKey, ops },
    }),
  reveal: (token: string, id: string, position: number) =>
    request<RevealResult>(`/v1/attempts/${encodeURIComponent(id)}/items/${position}/reveal`, { method: "POST", token }),
  result: (token: string, id: string, signal?: AbortSignal) =>
    request<AttemptResult>(`/v1/attempts/${encodeURIComponent(id)}/result`, { token, signal }),

  // Written practice (W03/W04/W06). Uploads are raw files; the server validates them, seals once with a receipt and
  // never marks anything before submission. Marks come from teachers (the supported route until B10).
  writtenAvailability: (token: string, grade: number, subject: string, signal?: AbortSignal) =>
    request<WrittenAvailability>(`/v1/written/availability?grade=${grade}&subject=${encodeURIComponent(subject)}`, { token, signal }),
  createWrittenForm: (token: string, idempotencyKey: string, body: Record<string, unknown>) =>
    request<WrittenForm>("/v1/written/forms", { method: "POST", token, body, headers: { "Idempotency-Key": idempotencyKey } }),
  startWritten: (token: string, formId: string) =>
    request<WrittenAttempt>(`/v1/written/forms/${encodeURIComponent(formId)}/attempt`, { method: "POST", token }),
  // W04.S3.T3 (MOBILE-LINKED-01): prepare a linked new practice test (nothing reserved yet); the key makes a retry
  // return the same prepared test.
  prepareLinkedPractice: (
    token: string,
    attemptId: string,
    idempotencyKey: string,
    body: { reason: "REWRITE" | "NEW_CONTENT" | "INDETERMINATE"; positions: number[]; revision_id: string | null },
  ) =>
    request<LinkedForm>(`/v1/written-attempts/${encodeURIComponent(attemptId)}/linked-forms`, {
      method: "POST",
      token,
      body,
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  linkedForm: (token: string, formId: string, signal?: AbortSignal) =>
    request<LinkedForm>(`/v1/written/linked-forms/${encodeURIComponent(formId)}`, { token, signal }),
  /** W03.S1.T3: turn, trim or clarify a page. `trim` (x, y, w, h of the page as shown) replaces `crop` when given. */
  transformPage: (
    token: string,
    attemptId: string,
    pageId: string,
    body: {
      rotate: number;
      crop: number[] | null;
      enhance: boolean;
      trim?: number[];
      straighten?: number | "auto"; // STRAIGHTEN-01, where rolled out
      shown_crop?: number[] | null;
    },
  ) =>
    request<WrittenPage>(`/v1/written-attempts/${encodeURIComponent(attemptId)}/pages/${encodeURIComponent(pageId)}/transform`, {
      method: "PUT",
      token,
      body,
    }),
  writtenAttempt: (token: string, id: string, signal?: AbortSignal) =>
    request<WrittenAttempt>(`/v1/written-attempts/${encodeURIComponent(id)}`, { token, signal }),
  uploadWritten: (token: string, id: string, file: Blob) =>
    request<{ pages: WrittenAttempt["pages"]; duplicate: boolean; warnings: string[] }>(
      `/v1/written-attempts/${encodeURIComponent(id)}/pages`,
      { method: "POST", token, raw: file },
    ),
  saveMapping: (token: string, id: string, expectedRevision: number, slots: Record<string, { pages: string[]; unanswered: boolean }>) =>
    request<WrittenAttempt>(`/v1/written-attempts/${encodeURIComponent(id)}/manifest`, {
      method: "PUT",
      token,
      body: { expected_revision: expectedRevision, slots },
    }),
  sealWritten: (token: string, id: string, idempotencyKey: string, expectedRevision: number) =>
    request<WrittenSeal>(`/v1/written-attempts/${encodeURIComponent(id)}/seal`, {
      method: "POST",
      token,
      body: { idempotency_key: idempotencyKey, expected_revision: expectedRevision },
    }),
  writtenResult: (token: string, id: string, signal?: AbortSignal) =>
    request<WrittenResult>(`/v1/written-attempts/${encodeURIComponent(id)}/result`, { token, signal }),
  requestRecheck: (token: string, id: string, reason: string, positions: number[]) =>
    request<unknown>(`/v1/written-attempts/${encodeURIComponent(id)}/recheck`, { method: "POST", token, body: { reason, positions } }),
  /** A clearer copy of one pending answer. One key per chosen file, so a retry never makes a second copy (RS31-01). */
  rescan: (token: string, id: string, position: number, file: Blob, idempotencyKey: string) =>
    request<{ id: string; replay: boolean; post_cutoff: boolean }>(
      `/v1/written-attempts/${encodeURIComponent(id)}/questions/${position}/rescan?note=${encodeURIComponent("Clearer copy")}`,
      { method: "POST", token, raw: file, headers: { "Idempotency-Key": idempotencyKey } },
    ),
  confirmUnanswered: (token: string, id: string, position: number) =>
    request<void>(`/v1/written-attempts/${encodeURIComponent(id)}/questions/${position}/confirm-unanswered`, { method: "POST", token }),

  // Notifications (P15.S1): the shared inbox. Push to this device needs builds and credentials (B07).
  notifications: (token: string, signal?: AbortSignal) => request<Inbox>("/v1/me/notifications?limit=50", { token, signal }),
  readNotification: (token: string, id: string) =>
    request<void>(`/v1/me/notifications/${encodeURIComponent(id)}/read`, { method: "POST", token }),
  readAllNotifications: (token: string) => request<void>("/v1/me/notifications/read-all", { method: "POST", token }),

  // Help articles (P15.S2): published, public, searchable.
  helpArticles: (q: string, signal?: AbortSignal) =>
    getJSON<HelpArticleSummary[]>(`/v1/help/articles?q=${encodeURIComponent(q)}`, signal),
  helpArticle: (slug: string, signal?: AbortSignal) =>
    getJSON<HelpArticle>(`/v1/help/articles/${encodeURIComponent(slug)}`, signal),

  // Help (P15.S3): the learner's own requests and replies.
  tickets: (token: string, signal?: AbortSignal) => request<SupportTicket[]>("/v1/support/tickets", { token, signal }),
  ticket: (token: string, id: string, signal?: AbortSignal) =>
    request<SupportTicket>(`/v1/support/tickets/${encodeURIComponent(id)}`, { token, signal }),
  openTicket: (token: string, body: { category: string; subject: string; body: string; reference?: Record<string, unknown> }) =>
    request<SupportTicket>("/v1/support/tickets", { method: "POST", token, body }),
  replyTicket: (token: string, id: string, body: string) =>
    request<SupportTicket>(`/v1/support/tickets/${encodeURIComponent(id)}/messages`, { method: "POST", token, body: { body } }),
  // P15.S3.T1 (MOBILE-SCREENSHOTS-01): a JPEG or PNG, sent as is; the server validates and re-encodes it.
  addScreenshot: (token: string, id: string, file: Blob) =>
    request<NonNullable<SupportTicket["attachments"]>[number]>(`/v1/support/tickets/${encodeURIComponent(id)}/attachments`, {
      method: "POST",
      token,
      raw: file,
    }),
};

export const GRADE_LABEL: Record<number, string> = { 11: "Class XI", 12: "Class XII" };

export const SUBJECTS = [
  ["biology", "Biology"],
  ["chemistry", "Chemistry"],
  ["physics", "Physics"],
  ["computer_science", "Computer Science"],
  ["mathematics", "Mathematics"],
] as const;
export type SubjectCode = (typeof SUBJECTS)[number][0];

export function pageRange(start?: number | null, end?: number | null): string {
  if (start == null && end == null) return "unknown";
  if (start === end) return `${start}`;
  return `${start ?? "?"}–${end ?? "?"}`;
}
