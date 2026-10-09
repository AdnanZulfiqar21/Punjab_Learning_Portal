// Progress report on native (P12.S4.T2): the same figures and definitions as the web report.
import { Stack } from "expo-router";
import { ScrollView, View } from "react-native";

import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

export default function ProgressScreen() {
  const { state } = useAuth();
  const c = useTheme();
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      <Stack.Screen options={{ title: "Progress" }} />
      {state.status === "signed_in" ? <Report token={state.token} /> : <Notice title="Sign in to see your progress">Open the Account tab to sign in.</Notice>}
    </ScrollView>
  );
}

function Report({ token }: { token: string }) {
  const req = useRequest((signal) => api.progress(token, signal), [token]);
  if (req.state.status === "loading") return <Loading label="Preparing your report" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const r = req.state.data;
  return (
    <View style={{ gap: Space.md }}>
      <T variant="small">Prepared {when(r.generated_at)} · report version {r.report_version}</T>
      {r.subjects.length === 0 && <Notice title="No submitted tests yet">Take a practice test to start your report.</Notice>}
      {r.subjects.map((s) => (
        <Card key={`${s.grade}-${s.subject}`}>
          <T style={{ fontWeight: "600" }}>
            {GRADE_LABEL[s.grade]} {s.subject.replace("_", " ")}
          </T>
          <T variant="small">
            {s.tests} tests · {s.questions_answered} answered · {s.correct} correct · {s.accuracy === null ? "accuracy —" : `${s.accuracy}% accuracy`}
          </T>
        </Card>
      ))}
      <T variant="small">
        Notebook: {r.notebook.open} open · {r.notebook.mastered} mastered · {r.notebook.voided} withdrawn after review
      </T>
      <View style={{ gap: Space.xs }}>
        <T variant="heading">What these numbers mean</T>
        {Object.entries(r.definitions).map(([k, v]) => (
          <T key={k} variant="small">
            {k.replace("_", " ")}: {v}
          </T>
        ))}
        <T variant="small">This report counts what you did. It does not say which topics you have mastered.</T>
      </View>
    </View>
  );
}
