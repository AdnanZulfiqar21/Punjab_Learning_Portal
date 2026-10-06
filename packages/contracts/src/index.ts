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

/** RFC 9457 problem details returned by every API error. */
export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  correlation_id?: string | null;
  errors?: { loc: (string | number)[]; msg: string }[];
}
