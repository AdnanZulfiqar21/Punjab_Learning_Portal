// Shared labels for the lecture production pages (LECTURE-01).
export const LANGUAGE: Record<string, string> = { roman_ur: "Roman Urdu", ur: "Urdu", en: "English" };
export const STATUS: Record<string, string> = {
  in_production: "In production",
  in_review: "In academic review",
  approved: "Academically approved",
  changes_requested: "Changes requested",
};
export const CHECKS: [string, string][] = [
  ["accuracy", "Accuracy against the storyboard and textbook"],
  ["voice_text_alignment", "Narration matches the transcript and captions"],
  ["pacing", "Pacing"],
  ["spelling", "Spelling (including Roman Urdu terms)"],
  ["diagrams", "Diagrams and on-screen equations"],
  ["captions", "Captions timing and text"],
  ["rights", "Rights for every asset used"],
  ["source_verification", "Textbook-source verification of every claim"],
];
