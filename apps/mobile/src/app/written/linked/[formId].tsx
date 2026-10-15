// W04.S3.T3 (MOBILE-LINKED-01): confirm a prepared linked practice test before it uses any allowance. Starting goes
// through the ordinary admission path (its own reservation); the earlier result never changes.
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";

import { Button, FormError } from "@/components/form";
import { ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canStart, LINKED_REASON } from "@/lib/linked-practice";

export default function LinkedPracticeScreen() {
  const { formId } = useLocalSearchParams<{ formId: string }>();
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  if (state.status !== "signed_in") return <Notice title="Sign in to continue">Open the Account tab to sign in.</Notice>;
  return <Confirm formId={formId} token={state.token} />;
}

function Confirm({ formId, token }: { formId: string; token: string }) {
  const req = useRequest((signal) => api.linkedForm(token, formId, signal), [token, formId]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (req.state.status === "loading") return <Loading label="Loading your new practice test" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const f = req.state.data;
  const started = f.started_attempt_id;

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const a = await api.startWritten(token, f.form_id);
      router.replace({ pathname: "/written/[id]", params: { id: a.id } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The test couldn't be started. Nothing was charged; try again later.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      <Stack.Screen options={{ title: "New practice test" }} />
      <T variant="heading" accessibilityRole="header">
        New practice test
      </T>
      {started ? (
        <>
          <Notice title="Already started">This practice test has started.</Notice>
          <Button label="Open it" onPress={() => router.replace({ pathname: "/written/[id]", params: { id: started } })} />
        </>
      ) : (
        <>
          <T>{LINKED_REASON[f.linked_from.reason]}</T>
          <View style={{ gap: Space.xs }}>
            <T variant="small">
              Questions: {f.question_count} (question {f.linked_from.positions.join(", ")} of your earlier test)
            </T>
            <T variant="small">
              Allowance used when you start: {f.allowance_units} unit{f.allowance_units === 1 ? "" : "s"} (you have {f.allowance_available})
            </T>
          </View>
          <Notice title="Your earlier result stays as it is">
            This is a separate test with its own marks. It doesn&apos;t replace or change the marks on your earlier test, and it isn&apos;t a recheck.
          </Notice>
          <FormError message={error} />
          {canStart(f) ? (
            <Button label="Start the practice test" onPress={() => void start()} busy={busy} />
          ) : (
            <Notice tone="warn" title="Not enough allowance">
              Starting it needs {f.allowance_units} unit{f.allowance_units === 1 ? "" : "s"} of written allowance and you have {f.allowance_available}.
            </Notice>
          )}
        </>
      )}
    </ScrollView>
  );
}
