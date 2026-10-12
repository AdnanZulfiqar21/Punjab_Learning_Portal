import { router, Stack, useLocalSearchParams } from "expo-router";
import { ScrollView, View } from "react-native";
import type { ItemReview } from "@portal/contracts";

import { Button } from "@/components/form";
import { LessonBlocks, type AssetSource } from "@/components/lesson-blocks";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { MockRunningNotice, mockRunning } from "@/components/mock-running";
import { Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, attemptAsset } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TIME_ZONE } from "@/lib/dates";

type Blocks = { type: string }[];

// P11.S3.T3 (RECEIPT-01): why a learner's latest change to a question wasn't counted.
const WHY: Record<string, string> = {
  late: "arrived after the time was up",
  finalised: "arrived after the test was submitted",
  invalid: "wasn't a valid option",
};

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
  if (req.state.status === "error") {
    const reason = (req.state.error.problem as { code_reason?: string } | null | undefined)?.code_reason;
    if (reason === "RESULTS_PENDING" || reason === "SCORING_PENDING") {
      // Submitted and saved: a held scheduled mock, or a result still being prepared (OCT9-01, P10.S3.T3).
      return (
        <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg }}>
          <Stack.Screen options={{ title: "Your result" }} />
          <Notice title={reason === "SCORING_PENDING" ? "Submitted: your result is being prepared" : "Your answers are saved"}>
            {req.state.error.message}
          </Notice>
        </ScrollView>
      );
    }
    const running = mockRunning(req.state.error);
    if (running) return <MockRunningNotice attemptId={running} />;
    return <ErrorState error={req.state.error} onRetry={req.retry} />;
  }
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
      {r.revised_at && (
        <Notice title={`Updated ${new Date(r.revised_at).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE })}`}>
          {`${r.revision_reason ?? ""} Your earlier result stays in your history.`}
        </Notice>
      )}
      <T variant="small">
        {r.answered} of {r.question_count} answered · {r.finalise_reason === "expiry" ? "submitted when time ran out" : "submitted by you"}
      </T>
      {(r.not_counted ?? []).length > 0 && (
        <Notice title="Some last changes weren't counted" tone="warn">
          {(r.not_counted ?? [])
            .map((n) => `Question ${n.position}: your last change ${WHY[n.reason] ?? "wasn't counted"}.`)
            .join(" ")}{" "}
          The answer you had saved before it, if any, was marked.
        </Notice>
      )}
      {r.items.map((it) => (
        <Review key={it.position} item={it} assetSource={(v) => attemptAsset(id, v, token)} />
      ))}
      <Button variant="secondary" label="Practise again" onPress={() => router.navigate("/practice")} />
    </ScrollView>
  );
}

function Review({ item, assetSource }: { item: ItemReview; assetSource: AssetSource }) {
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
      {item.passage ? (
        <View accessibilityLabel="Passage" style={{ backgroundColor: c.surfaceMuted, borderRadius: Radius.sm, padding: Space.md }}>
          <LessonBlocks blocks={item.passage.blocks as Blocks} assetSource={assetSource} />
        </View>
      ) : null}
      <LessonBlocks blocks={item.stem as Blocks} assetSource={assetSource} />
      {item.options.map((o, i) => {
        const isKey = o.id === item.correct_option_id;
        const isChosen = o.id === item.chosen;
        return (
          <View key={o.id} style={{ flexDirection: "row", gap: Space.sm, padding: Space.sm, borderRadius: Radius.sm, borderWidth: 1, borderColor: isKey ? c.accent : isChosen ? c.danger : c.border, marginTop: Space.xs }}>
            <T style={{ fontWeight: "600", width: 20 }}>{String.fromCharCode(65 + i)}</T>
            <View style={{ flex: 1, gap: 2 }}>
              <LessonBlocks blocks={o.blocks as Blocks} assetSource={assetSource} />
              {isKey && <T variant="small" style={{ color: c.accent }}>Correct answer</T>}
              {isChosen && !isKey && <T variant="small" style={{ color: c.danger }}>Your answer{explanation.distractors?.[o.id] ? `: ${explanation.distractors[o.id]}` : ""}</T>}
            </View>
          </View>
        );
      })}
      {(explanation.correct?.length ?? 0) > 0 && (
        <View style={{ marginTop: Space.sm, padding: Space.sm, borderRadius: Radius.sm, backgroundColor: c.surfaceMuted }}>
          <T style={{ fontWeight: "600" }}>Why</T>
          <LessonBlocks blocks={explanation.correct ?? []} assetSource={assetSource} />
        </View>
      )}
      {(item.related_lessons ?? []).length > 0 && (
        // P13.S2.T3: the lessons that teach this question's topic (same as the web result), for revision.
        <View style={{ marginTop: Space.sm, gap: Space.xs }}>
          <T variant="small" style={{ fontWeight: "600" }}>
            Revise
          </T>
          {(item.related_lessons ?? []).map((l) => (
            <Button
              key={l.id}
              variant="link"
              label={l.title}
              onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: l.chapter_id } })}
            />
          ))}
        </View>
      )}
    </Card>
  );
}
