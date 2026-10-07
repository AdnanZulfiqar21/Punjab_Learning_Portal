import { router, Stack, useLocalSearchParams } from "expo-router";
import { ScrollView, View } from "react-native";
import type { ItemReview } from "@portal/contracts";

import { Button } from "@/components/form";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Blocks = { type: string }[];

export default function ResultScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  if (state.status !== "signed_in") return <Notice title="Sign in to continue">Open the Account tab to sign in.</Notice>;
  return <ResultView id={id} token={state.token} />;
}

function ResultView({ id, token }: { id: string; token: string }) {
  const c = useTheme();
  const req = useRequest((signal) => api.result(token, id, signal), [token, id]);
  if (req.state.status === "loading") return <Loading label="Loading your result" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const r = req.state.data;
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: "Your result" }} />
      {r.status === "not_scorable" ? (
        <Notice tone="warn" title="This test can't be scored">
          Every question was withdrawn after review, so there is nothing to score.
        </Notice>
      ) : (
        <View>
          <T variant="title">
            {r.raw} / {r.maximum}
          </T>
          {r.percentage !== null && <T variant="muted">{String(r.percentage)}%</T>}
        </View>
      )}
      <T variant="small">
        {r.answered} of {r.question_count} answered · {r.finalise_reason === "expiry" ? "submitted when time ran out" : "submitted by you"}
      </T>
      {r.items.map((it) => (
        <Review key={it.position} item={it} />
      ))}
      <Button variant="secondary" label="Practise again" onPress={() => router.navigate("/practice")} />
    </ScrollView>
  );
}

function Review({ item }: { item: ItemReview }) {
  const c = useTheme();
  const explanation = item.explanation as { correct?: Blocks; distractors?: Record<string, string> };
  return (
    <Card>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <T variant="heading">Question {item.position}</T>
        {item.treatment !== "NONE" ? (
          <Badge tone="warn">{item.treatment === "EXCLUDE" ? "Excluded" : item.treatment === "CREDIT_ALL" ? "Credited" : "Key corrected"}</Badge>
        ) : item.chosen === null ? (
          <Badge>Not answered</Badge>
        ) : item.correct ? (
          <Badge>Correct</Badge>
        ) : (
          <Badge tone="warn">Incorrect</Badge>
        )}
      </View>
      <LessonBlocks blocks={item.stem as Blocks} />
      {item.options.map((o, i) => {
        const isKey = o.id === item.correct_option_id;
        const isChosen = o.id === item.chosen;
        return (
          <View key={o.id} style={{ flexDirection: "row", gap: Space.sm, padding: Space.sm, borderRadius: Radius.sm, borderWidth: 1, borderColor: isKey ? c.accent : isChosen ? c.danger : c.border, marginTop: Space.xs }}>
            <T style={{ fontWeight: "600", width: 20 }}>{String.fromCharCode(65 + i)}</T>
            <View style={{ flex: 1, gap: 2 }}>
              <LessonBlocks blocks={o.blocks as Blocks} />
              {isKey && <T variant="small" style={{ color: c.accent }}>Correct answer</T>}
              {isChosen && !isKey && <T variant="small" style={{ color: c.danger }}>Your answer{explanation.distractors?.[o.id] ? `: ${explanation.distractors[o.id]}` : ""}</T>}
            </View>
          </View>
        );
      })}
      {(explanation.correct?.length ?? 0) > 0 && (
        <View style={{ marginTop: Space.sm, padding: Space.sm, borderRadius: Radius.sm, backgroundColor: c.surfaceMuted }}>
          <T style={{ fontWeight: "600" }}>Why</T>
          <LessonBlocks blocks={explanation.correct ?? []} />
        </View>
      )}
    </Card>
  );
}
