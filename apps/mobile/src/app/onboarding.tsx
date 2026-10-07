import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";
import type { Profile, ProfileInput } from "@portal/contracts";

import { Button, Choices, Field, FormError } from "@/components/form";
import { Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Subject = NonNullable<ProfileInput["subjects"]>[number];
type Exam = NonNullable<ProfileInput["target_exams"]>[number];
type Stream = NonNullable<ProfileInput["stream"]>;
type Language = NonNullable<ProfileInput["explanation_language"]>;

const GRADES = [
  [11, "Class XI"],
  [12, "Class XII"],
] as const;
const STREAMS: readonly (readonly [Stream | "", string])[] = [
  ["pre_medical", "Pre-Medical"],
  ["pre_engineering", "Pre-Engineering"],
  ["ics", "ICS"],
  ["", "Not sure yet"],
];
const SUBJECTS: readonly (readonly [Subject, string])[] = [
  ["biology", "Biology"],
  ["chemistry", "Chemistry"],
  ["physics", "Physics"],
  ["computer_science", "Computer Science"],
  ["mathematics", "Mathematics"],
];
const EXAMS: readonly (readonly [Exam, string])[] = [
  ["mdcat", "MDCAT"],
  ["ecat", "ECAT"],
];
const LANGUAGES: readonly (readonly [Language, string])[] = [
  ["en", "English"],
  ["ur", "Urdu"],
  ["roman_ur", "Roman Urdu"],
];

const toggle = <V,>(list: V[], v: V) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

export default function OnboardingScreen() {
  const c = useTheme();
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  if (state.status !== "signed_in") {
    return (
      <View style={{ flex: 1, padding: Space.lg, gap: Space.lg, backgroundColor: c.background }}>
        <Notice title="Sign in first">Sign in from the Account tab to set up your learning preferences.</Notice>
        <Button label="Go to Account" onPress={() => router.replace("/account")} />
      </View>
    );
  }
  return <ProfileForm token={state.token} profile={state.me.profile ?? null} />;
}

function ProfileForm({ token, profile }: { token: string; profile: Profile | null }) {
  const c = useTheme();
  const { refresh, handleError } = useAuth();
  const [grade, setGrade] = useState<11 | 12 | null>((profile?.grade as 11 | 12 | null | undefined) ?? null);
  const [stream, setStream] = useState<Stream | "">(profile?.stream ?? "");
  const [subjects, setSubjects] = useState<Subject[]>((profile?.subjects as Subject[] | undefined) ?? []);
  const [exams, setExams] = useState<Exam[]>((profile?.target_exams as Exam[] | undefined) ?? []);
  const [language, setLanguage] = useState<Language>((profile?.explanation_language as Language | undefined) ?? "en");
  const [year, setYear] = useState(profile?.target_year ? String(profile.target_year) : "");
  const [minutes, setMinutes] = useState(profile?.daily_minutes ? String(profile.daily_minutes) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setError(null);
    if (!grade) return setError("Choose your class.");
    const body: ProfileInput = {
      grade,
      stream: stream || null,
      subjects,
      target_exams: exams,
      target_year: year ? Number(year) : null,
      explanation_language: language,
      daily_minutes: minutes ? Number(minutes) : null,
    };
    setBusy(true);
    try {
      await api.saveProfile(token, body);
      await refresh();
      router.back();
    } catch (e) {
      handleError(e);
      const errs = e instanceof ApiError ? (e.problem?.errors ?? []) : [];
      setError(
        errs.length
          ? `Please check: ${errs.map((x) => `${String(x.loc.at(-1)).replace("_", " ")}: ${x.msg}`).join("; ")}`
          : e instanceof ApiError && e.kind === "offline"
            ? e.message
            : "Could not save your preferences.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      style={{ backgroundColor: c.background }}
      contentContainerStyle={{ padding: Space.lg, gap: Space.xl, paddingBottom: Space.xxl * 2 }}>
      <View style={{ gap: Space.xs }}>
        <T variant="title">Set up your learning</T>
        <T variant="muted">You can change any of this later. We never ask for CNIC or other identity documents.</T>
      </View>
      <Choices label="Which class are you in?" options={GRADES} selected={grade ? [grade] : []} onToggle={(v) => setGrade(v)} />
      <Choices label="Group" options={STREAMS} selected={[stream]} onToggle={(v) => setStream(v)} />
      <Choices label="Subjects" options={SUBJECTS} selected={subjects} onToggle={(v) => setSubjects(toggle(subjects, v))} multiple />
      <View style={{ gap: Space.sm }}>
        <Choices
          label="Preparing for an entry test?"
          options={EXAMS}
          selected={exams}
          onToggle={(v) => setExams(toggle(exams, v))}
          multiple
        />
        <T variant="small">
          Full official-pattern mocks also need English (and Logical Reasoning for MDCAT), which are not part of this
          portal yet. Subject practice for your five subjects is available.
        </T>
      </View>
      <Field label="Test year" value={year} onChangeText={setYear} keyboardType="number-pad" maxLength={4} placeholder="e.g. 2027" />
      <Choices label="Explanations in" options={LANGUAGES} selected={[language]} onToggle={(v) => setLanguage(v)} />
      <Field label="Minutes per day" value={minutes} onChangeText={setMinutes} keyboardType="number-pad" maxLength={3} placeholder="e.g. 60" />
      <FormError message={error} />
      <Button label="Save" onPress={save} busy={busy} />
    </ScrollView>
  );
}
