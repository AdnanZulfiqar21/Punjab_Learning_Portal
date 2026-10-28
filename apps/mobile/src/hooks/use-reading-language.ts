// The reader's language (English or Roman Urdu), shared by a topic's lesson and a book exercise: this device's choice,
// else the profile's explanation language, else English. A new choice is kept on the device and, for a signed-in
// learner, in the profile through the existing profile service.
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";
import { preferredLanguage, type ReadingLanguage } from "@/lib/reading-language-core";

export function useReadingLanguage(): { language: ReadingLanguage; choose: (next: ReadingLanguage) => void } {
  const auth = useAuth();
  const { prefs, update } = usePrefs();
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  const me = auth.state.status === "signed_in" ? auth.state.me : null;
  const language = preferredLanguage(prefs.language, me?.profile?.explanation_language);

  function choose(next: ReadingLanguage) {
    update({ language: next });
    const p = me?.profile;
    if (token && p?.grade) {
      // Keep the choice with the account too (existing profile service); the device copy already applies.
      void api
        .saveProfile(token, {
          grade: p.grade,
          stream: p.stream ?? null,
          subjects: p.subjects ?? [],
          target_exams: p.target_exams ?? [],
          target_year: p.target_year ?? null,
          explanation_language: next,
          daily_minutes: p.daily_minutes ?? null,
        })
        .then(() => auth.refresh())
        .catch(auth.handleError);
    }
  }

  return { language, choose };
}
