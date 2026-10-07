// Stable aliases over the generated OpenAPI types. Regenerate with `pnpm --filter @portal/contracts generate`.
import type { components, paths } from "./generated";

export type { components, paths };
type S = components["schemas"];

export type Catalogue = S["CatalogueOut"];
export type GradeCatalogue = S["GradeCatalogue"];
export type Book = S["BookOut"];
export type ChapterSummary = S["ChapterSummary"];
export type Chapter = S["ChapterOut"];
export type TopicNode = S["TopicNode"];
export type SourceRef = S["SourceRef"];
export type SearchResult = S["SearchOut"];
export type SearchHit = S["SearchHit"];
export type RuntimeConfig = S["RuntimeConfig"];
export type Me = S["MeOut"];
export type Profile = S["ProfileOut"];
export type ProfileInput = S["ProfileIn"];
export type Consent = S["ConsentOut"];
export type RoleGrant = S["RoleGrantOut"];
export type AppSession = S["SessionOut"];
export type SessionCreated = S["SessionCreatedOut"];
export type StudioItemSummary = S["ItemSummary"];
export type StudioItem = S["ItemDetail"];
export type StudioActions = S["Actions"];
export type ContentVersion = S["VersionOut"];
export type ContentReview = S["ReviewOut"];
export type SourceInfo = S["SourceOut"];
export type StudioHistoryEvent = S["HistoryEvent"];
export type ContentValidation = S["ValidationOut"];
export type Lesson = S["LessonOut"];
export type PracticeAvailability = S["AvailabilityOut"];
export type PracticeForm = S["FormOut"];
export type PracticeAttempt = S["AttemptOut"];
export type AttemptItem = S["ItemSnapshot"];
export type AttemptAnswer = S["AnswerOut"];
export type AnswerOpResult = S["OpResult"];
export type SaveResult = S["SaveOut"];
export type SubmitResult = S["SubmitOut"];
export type SubmissionReceipt = S["ReceiptOut"];
export type AttemptResult = S["ResultOut"];
export type ItemReview = S["ItemReview"];
export type RevealResult = S["RevealOut"];

/** RFC 9457 problem details returned by every API error. */
export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  correlation_id?: string | null;
  errors?: { loc: (string | number)[]; msg: string }[];
}
