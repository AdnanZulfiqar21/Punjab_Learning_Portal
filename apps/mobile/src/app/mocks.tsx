// Mock tests on native (P09.S2/S2.T3): published official patterns and scheduled windows, as on the web.
import { router, Stack } from "expo-router";
import { useRef, useState } from "react";
import { ScrollView, View } from "react-native";

import { Button, FormError } from "@/components/form";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const newKey = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

export default function MocksScreen() {
  const { state } = useAuth();
  const c = useTheme();
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      <Stack.Screen options={{ title: "Mock tests" }} />
      <T variant="muted">Full-length tests that follow an official pattern checked by two reviewers. Taking a mock doesn&apos;t affect admission eligibility.</T>
      {state.status === "signed_in" ? <Mocks token={state.token} /> : <Notice title="Sign in to take a mock">Open the Account tab to sign in.</Notice>}
    </ScrollView>
  );
}

function Mocks({ token }: { token: string }) {
  const { handleError } = useAuth();
  const profiles = useRequest((signal) => api.examProfiles(token, signal), [token]);
  const sessions = useRequest((signal) => api.mockSessions(token, signal), [token]);
  const key = useRef<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function go(id: string, fn: () => Promise<string>) {
    setBusy(id);
    setError(null);
    try {
      const attemptId = await fn();
      router.push({ pathname: "/attempt/[id]", params: { id: attemptId } });
    } catch (e) {
      key.current = null;
      if (e instanceof ApiError) setError(e.message);
      else handleError(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <View style={{ gap: Space.md }}>
      <FormError message={error} />
      {sessions.state.status === "success" && sessions.state.data.length > 0 && (
        <View style={{ gap: Space.sm }}>
          <T variant="heading">Scheduled mocks</T>
          {sessions.state.data.map((s) => (
            <Card key={s.id}>
              <T style={{ fontWeight: "600" }}>{s.title}</T>
              <T variant="small">
                {s.profile_name} · starts {when(s.starts_at)} · late entry until {when(s.entry_closes_at)} · results {when(s.results_at)}
              </T>
              {s.state === "open" && (
                <View style={{ marginTop: Space.sm, alignSelf: "flex-start" }}>
                  <Button
                    label="Join now"
                    busy={busy === s.id}
                    onPress={() => go(s.id, async () => (await api.joinSession(token, s.id)).attempt_id)}
                  />
                </View>
              )}
            </Card>
          ))}
        </View>
      )}
      {profiles.state.status === "loading" && <Loading label="Loading test patterns" />}
      {profiles.state.status === "error" && <ErrorState error={profiles.state.error} onRetry={profiles.retry} />}
      {profiles.state.status === "success" && profiles.state.data.length === 0 && (
        <Notice title="No mock tests yet">Mock tests appear once an official pattern has been checked by two reviewers.</Notice>
      )}
      {profiles.state.status === "success" &&
        profiles.state.data.map((p) => (
          <Card key={p.code}>
            <T style={{ fontWeight: "600" }}>
              {p.name} · {p.year}
            </T>
            <T variant="small">
              {p.total_questions} questions · {p.duration_minutes} minutes
            </T>
            <View style={{ marginTop: Space.sm, alignSelf: "flex-start" }}>
              <Button
                label="Start mock (timed)"
                busy={busy === p.code}
                onPress={() =>
                  go(p.code, async () => {
                    key.current ??= newKey();
                    const form = await api.createMock(token, key.current, p.code);
                    return (await api.startAttempt(token, form.id)).id;
                  })
                }
              />
            </View>
          </Card>
        ))}
    </View>
  );
}
