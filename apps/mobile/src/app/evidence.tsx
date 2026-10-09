// Evidence on native (P12.S2, EVIDENCE-RULES-01): the same rules, states and meters as the web page.
import { Stack } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";

import { Choices } from "@/components/form";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, SUBJECTS, type SubjectCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STATE: Record<string, { label: string; tone: "info" | "warn" }> = {
  demonstrated: { label: "Demonstrated", tone: "info" },
  developing: { label: "Developing", tone: "warn" },
  insufficient_evidence: { label: "Not enough evidence yet", tone: "info" },
};
const GRADES = [
  [11, "Class XI"],
  [12, "Class XII"],
] as const;

export default function EvidenceScreen() {
  const { state } = useAuth();
  const c = useTheme();
  const [grade, setGrade] = useState<11 | 12>(11);
  const [subject, setSubject] = useState<SubjectCode>("biology");
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      <Stack.Screen options={{ title: "What you've shown" }} />
      <T variant="muted">
        Each topic is judged from your answers in the last 90 days. Repeating the same question doesn&apos;t count as new evidence. These are transparent rules, not a guarantee of exam
        results.
      </T>
      {state.status === "signed_in" ? (
        <>
          <Choices label="Class" options={GRADES} selected={[grade]} onToggle={setGrade} />
          <Choices label="Subject" options={SUBJECTS} selected={[subject]} onToggle={setSubject} />
          <Report token={state.token} grade={grade} subject={subject} />
        </>
      ) : (
        <Notice title="Sign in to see your evidence">Open the Account tab to sign in.</Notice>
      )}
    </ScrollView>
  );
}

function Report({ token, grade, subject }: { token: string; grade: number; subject: string }) {
  const req = useRequest((signal) => api.evidence(token, grade, subject, signal), [token, grade, subject]);
  if (req.state.status === "loading") return <Loading label="Working out your evidence" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const r = req.state.data;
  return (
    <View style={{ gap: Space.md }}>
      {Object.entries(r.meters).map(([k, m]) => {
        const meter = m as { value: number | null; definition: string };
        return (
          <Card key={k}>
            <T variant="small">{k.replace(/_/g, " ")}</T>
            <T style={{ fontWeight: "600" }}>{meter.value === null ? "Unavailable" : `${meter.value}%`}</T>
            <T variant="small">{meter.definition}</T>
          </Card>
        );
      })}
      {r.outcomes.length === 0 && <Notice title="No topics yet">This book has no topics to judge yet.</Notice>}
      {r.outcomes.map((o) => (
        <Card key={o.outcome_id}>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.sm, alignItems: "center" }}>
            <Badge tone={STATE[o.state]?.tone ?? "info"}>{STATE[o.state]?.label ?? o.state}</Badge>
            <T style={{ flexShrink: 1 }}>
              Chapter {o.chapter_number} · {o.label}
            </T>
          </View>
          {o.reasons.length > 0 && <T variant="small">{o.reasons.join(" ")}</T>}
          {o.total_weight > 0 && (
            <T variant="small">
              Evidence weight {o.total_weight} from {o.families} question families
              {o.weighted_accuracy !== null && ` · ${Math.round(o.weighted_accuracy * 100)}% weighted accuracy`} · first-time evidence {o.independent_weight}
            </T>
          )}
        </Card>
      ))}
      <T variant="small">
        Rules: {r.rules_version}, evaluated {new Date(r.evaluated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}.
      </T>
    </View>
  );
}
