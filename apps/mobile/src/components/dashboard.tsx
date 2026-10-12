// Learner dashboard on native (P11.S1.T2, DASHBOARD-01): the same figures and definitions as the web home. The three
// meters stay separate; a meter without a verified denominator says why instead of showing a percentage.
import type { Dashboard } from "@portal/contracts";
import { router } from "expo-router";
import { View } from "react-native";

import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { api, GRADE_LABEL } from "@/lib/api";

const METER_LABEL: Record<Dashboard["meters"][number]["key"], string> = {
  syllabus_coverage: "Syllabus coverage",
  content_completed: "Content completed",
  demonstrated_knowledge: "Demonstrated knowledge",
};

export function DashboardSection({ token }: { token: string }) {
  const req = useRequest((signal) => api.dashboard(token, signal), [token]);
  const feats = useRequest((signal) => api.features(token, signal), [token]);
  const studyTools = feats.state.status === "success" && feats.state.data.study_tools === true; // ROLLOUT-01
  if (req.state.status === "loading") return <Loading label="Loading your dashboard" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const d = req.state.data;
  const next = d.continue_learning;
  return (
    <View style={{ gap: Space.sm }}>
      <T variant="heading" accessibilityRole="header">
        Your dashboard
      </T>
      {!d.profile && <Notice title="Choose your class and subjects">Set up your profile in the Account tab to see your meters.</Notice>}
      {studyTools && (
        <Card label="My study tools: notes, favourite topics and saved formulas" onPress={() => router.push("/study")}>
          <T style={{ fontWeight: "600" }}>My study tools</T>
          <T variant="small">Notes, favourite topics and saved formulas</T>
        </Card>
      )}
      {next ? (
        <Card label={`Continue learning: ${next.title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: next.chapter_id } })}>
          <T variant="small">Continue learning</T>
          <T style={{ fontWeight: "600" }}>{next.title}</T>
          <T variant="small">
            {GRADE_LABEL[next.grade]} · Chapter {next.chapter_number}: {next.chapter_title}
          </T>
        </Card>
      ) : null}
      <Card label={`Today's revision: ${d.revision.due} due`} onPress={() => router.push("/notebook")}>
        <T variant="small">Today&apos;s revision</T>
        <T>
          {d.revision.due === 0 ? "Nothing due today." : `${d.revision.due} mistake${d.revision.due === 1 ? "" : "s"} due for review.`} {d.revision.open} open.
        </T>
      </Card>
      {d.upcoming_mock && (
        <Card label={`Upcoming mock: ${d.upcoming_mock.title}`} onPress={() => router.push("/mocks")}>
          <T variant="small">Upcoming mock</T>
          <T style={{ fontWeight: "600" }}>{d.upcoming_mock.title}</T>
        </Card>
      )}
      {d.meters.map((m) => (
        <Card key={m.key} label={`${METER_LABEL[m.key]}: ${m.percent === null ? `unavailable. ${m.unavailable}` : `${m.percent}%, ${m.numerator} of ${m.denominator}`}`}>
          <T style={{ fontWeight: "600" }}>{METER_LABEL[m.key]}</T>
          {m.percent === null ? (
            <T>Unavailable. {m.unavailable}</T>
          ) : (
            <T>
              {m.percent}% ({m.numerator} of {m.denominator})
            </T>
          )}
          <T variant="small">{m.definition}</T>
        </Card>
      ))}
      {d.results_pending > 0 && (
        <T variant="small">
          {d.results_pending} scheduled mock result{d.results_pending === 1 ? " is" : "s are"} waiting for release.
        </T>
      )}
      {d.recent.map((t) => (
        <Card key={t.attempt_id} label={`Result: ${t.raw} of ${t.maximum}`} onPress={() => router.push({ pathname: "/result/[id]", params: { id: t.attempt_id } })}>
          <T variant="small">
            {t.kind === "mock" ? "Mock" : t.kind === "review" ? "Review" : "Practice"} · {t.parts.map((x) => `${GRADE_LABEL[x.grade]} ${x.subject.replace("_", " ")}`).join(" + ")}
          </T>
          <T>{t.status === "not_scorable" ? "Not scorable" : `${t.raw} / ${t.maximum}${t.percentage === null ? "" : ` (${t.percentage}%)`}`}</T>
        </Card>
      ))}
    </View>
  );
}
