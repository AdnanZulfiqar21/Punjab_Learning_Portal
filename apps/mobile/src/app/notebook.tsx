// Mistake notebook on native (P12.S3): due questions come back after 1, 3, 7 and 14 days.
import { router, Stack } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";

import { Button, FormError } from "@/components/form";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const newKey = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;

export default function NotebookScreen() {
  const { state } = useAuth();
  const c = useTheme();
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      <Stack.Screen options={{ title: "Mistake notebook" }} />
      <T variant="muted">Questions you answered wrongly come back after 1, 3, 7 and 14 days. Miss one again and it starts over.</T>
      {state.status === "signed_in" ? <Entries token={state.token} /> : <Notice title="Sign in to see your notebook">Open the Account tab to sign in.</Notice>}
    </ScrollView>
  );
}

function Entries({ token }: { token: string }) {
  const { handleError } = useAuth();
  const req = useRequest((signal) => api.notebook(token, signal), [token]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (req.state.status === "loading") return <Loading label="Loading your notebook" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const entries = req.state.data;
  if (entries.length === 0) return <Notice title="Nothing here yet">Questions you get wrong in a practice test appear here.</Notice>;
  const due = new Map<string, number>();
  for (const e of entries) if (e.due) due.set(`${e.grade}:${e.subject}`, (due.get(`${e.grade}:${e.subject}`) ?? 0) + 1);

  async function review(grade: number, subject: string) {
    const k = `${grade}:${subject}`;
    setBusy(k);
    setError(null);
    try {
      const form = await api.reviewTest(token, newKey(), grade, subject);
      const attempt = await api.startAttempt(token, form.id);
      router.push({ pathname: "/attempt/[id]", params: { id: attempt.id } });
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else handleError(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <View style={{ gap: Space.md }}>
      <FormError message={error} />
      {[...due.entries()].map(([k, n]) => {
        const [grade, subject] = k.split(":");
        return (
          <Card key={k}>
            <T>
              {GRADE_LABEL[Number(grade)]} {subject.replace("_", " ")}: {n} due
            </T>
            <View style={{ marginTop: Space.sm, alignSelf: "flex-start" }}>
              <Button label="Review now" busy={busy === k} onPress={() => review(Number(grade), subject)} />
            </View>
          </Card>
        );
      })}
      {entries.map((e) => (
        <Card key={e.id}>
          <View style={{ flexDirection: "row", gap: Space.sm, flexWrap: "wrap" }}>
            <Badge tone={e.due ? "warn" : "info"}>{e.status === "open" ? (e.due ? "Due now" : "Waiting") : e.status}</Badge>
            <T variant="small">
              {GRADE_LABEL[e.grade]} {e.subject.replace("_", " ")} · missed {e.misses}
            </T>
          </View>
          <T variant="small">{e.why}</T>
          {e.note ? <T variant="small">Your note: {e.note}</T> : null}
        </Card>
      ))}
    </View>
  );
}
