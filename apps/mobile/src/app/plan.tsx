// Study plan on native (P12.S4.T1, STUDYPLAN-01): the same plan, shortfall and assumptions as the web page.
import { Stack } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";

import { Button, Choices, Field } from "@/components/form";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, SUBJECTS, type SubjectCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const GRADES = [
  [11, "Class XI"],
  [12, "Class XII"],
] as const;
const hours = (m: number) => (m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`);
const inDays = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
type Query = { grade: number; subject: string; target_date: string; daily_minutes: number };

export default function PlanScreen() {
  const { state } = useAuth();
  const c = useTheme();
  const [grade, setGrade] = useState<11 | 12>(11);
  const [subject, setSubject] = useState<SubjectCode>("biology");
  const [target, setTarget] = useState(inDays(60));
  const [minutes, setMinutes] = useState(state.status === "signed_in" ? String(state.me.profile?.daily_minutes ?? 60) : "60");
  const [query, setQuery] = useState<Query | null>(null);
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(target) && Number(minutes) >= 10 && Number(minutes) <= 600;
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.md }} keyboardShouldPersistTaps="handled">
      <Stack.Screen options={{ title: "Study plan" }} />
      <T variant="muted">
        A plan for one book up to your target date, weakest topics first. If there isn&apos;t enough time, it says so and shows what matters most. It doesn&apos;t predict exam results.
      </T>
      {state.status !== "signed_in" ? (
        <Notice title="Sign in to make a plan">Open the Account tab to sign in.</Notice>
      ) : (
        <>
          <Choices label="Class" options={GRADES} selected={[grade]} onToggle={setGrade} />
          <Choices label="Subject" options={SUBJECTS} selected={[subject]} onToggle={setSubject} />
          <Field label="Target date (YYYY-MM-DD)" value={target} onChangeText={setTarget} autoCapitalize="none" />
          <Field label="Minutes a day (10 to 600)" value={minutes} onChangeText={setMinutes} inputMode="numeric" />
          <Button label="Make my plan" disabled={!valid} onPress={() => setQuery({ grade, subject, target_date: target, daily_minutes: Number(minutes) })} />
          {query && <Plan token={state.token} query={query} />}
        </>
      )}
    </ScrollView>
  );
}

function Plan({ token, query }: { token: string; query: Query }) {
  const req = useRequest((signal) => api.studyPlan(token, query, signal), [token, query]);
  if (req.state.status === "loading") return <Loading label="Planning" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const p = req.state.data;
  return (
    <View style={{ gap: Space.md }}>
      {p.feasible ? (
        <Notice title="This fits your time">
          About {hours(p.required_minutes)} of work over {p.days} days, with {hours(p.available_minutes)} available.
        </Notice>
      ) : (
        <Notice tone="warn" title={`About ${hours(p.shortfall_minutes)} short`}>
          This book needs about {hours(p.required_minutes)} but {p.days} days at {p.daily_minutes} minutes a day give {hours(p.available_minutes)}. The plan covers the most
          important {p.schedule.length} topics; {p.unscheduled_topics} more won&apos;t fit unless you add time or move the date.
        </Notice>
      )}
      {p.schedule.map((x, i) => (
        <Card key={i}>
          <T style={{ fontWeight: "600" }}>
            {new Date(String(x.date)).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })} · Chapter {String(x.chapter_number)}
          </T>
          <T>{String(x.label)}</T>
          <T variant="small">
            {String(x.minutes)} min · {String(x.why)}
          </T>
        </Card>
      ))}
      <T variant="small">
        Estimates: {String(p.assumptions.developing_minutes)} minutes for a developing topic, {String(p.assumptions.no_evidence_minutes)} for one without evidence; order:{" "}
        {String(p.assumptions.order)}. The plan updates from your latest answers, so a missed day simply replans.
      </T>
    </View>
  );
}
