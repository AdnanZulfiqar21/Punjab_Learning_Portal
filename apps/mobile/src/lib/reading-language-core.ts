// Reader language (Class XI Biology Chapter 1 pilot): English or Roman Urdu explanations. Pure rules for tests.
//
// A lesson's Roman Urdu variant is a full explanation written for the topic, stored as its own content item and
// version (language `roman_ur`, grouped with the English item by concept). The API answers in the requested language
// when that variant exists and says so (`requested_language_missing`) when it falls back to English.

export type ReadingLanguage = "en" | "roman_ur";

export const READING_LANGUAGES: readonly (readonly [ReadingLanguage, string])[] = [
  ["en", "English"],
  ["roman_ur", "Roman Urdu"],
];

export function isReadingLanguage(value: unknown): value is ReadingLanguage {
  return value === "en" || value === "roman_ur";
}

/** The language to ask for: this device's choice, else the profile's explanation language, else English. */
export function preferredLanguage(device: unknown, profileLanguage: string | null | undefined): ReadingLanguage {
  if (isReadingLanguage(device)) return device;
  if (isReadingLanguage(profileLanguage)) return profileLanguage;
  return "en";
}

/** What to tell the reader when the lesson came back in another language than asked for. */
export function missingLanguageNote(requested: ReadingLanguage, shown: string, available: readonly string[]): string | null {
  if (requested === shown) return null;
  const wanted = requested === "roman_ur" ? "Roman Urdu" : "English";
  const got = shown === "roman_ur" ? "Roman Urdu" : shown === "ur" ? "Urdu" : "English";
  const also = available.filter((l) => l !== shown && l !== requested && l === "ur");
  return `${wanted} isn’t available for this topic yet. Showing ${got}.${also.length ? " Urdu is also available." : ""}`;
}
