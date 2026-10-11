// My study tools on native (STUDY-TOOLS-01): the same notes, favourite topics and saved formulas as the web /study page.
import { router, Stack } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";

import { Button } from "@/components/form";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function StudyScreen() {
  const { state } = useAuth();
  const c = useTheme();
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: "My study tools" }} />
      <T variant="muted">Your notes, favourite topics and saved formulas. Only you can see them.</T>
      {state.status === "signed_in" ? <Tools token={state.token} /> : <Notice title="Sign in to see your study tools">Open the Account tab to sign in.</Notice>}
    </ScrollView>
  );
}

function Tools({ token }: { token: string }) {
  const req = useRequest(
    async (signal) => {
      const [notes, favourites, formulas] = await Promise.all([api.notes(token, signal), api.favourites(token, signal), api.formulas(token, signal)]);
      return { notes, favourites, formulas };
    },
    [token],
  );
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  if (req.state.status === "loading") return <Loading label="Loading your study tools" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const { notes, favourites, formulas } = req.state.data;
  const subject = (s: string) => s.replace("_", " ");
  return (
    <View style={{ gap: Space.lg }}>
      <View style={{ gap: Space.sm }}>
        <T variant="heading" accessibilityRole="header">
          Notes
        </T>
        {notes.length === 0 && <T variant="muted">No notes yet. Add a private note under any lesson you can read.</T>}
        {notes.map((n) => (
          <Card key={n.lesson_id} label={`Note on ${n.lesson_title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: n.chapter_id } })}>
            <T style={{ fontWeight: "600" }}>{n.lesson_title}</T>
            <T variant="small">
              {GRADE_LABEL[n.grade]} {subject(n.subject)} · Chapter {n.chapter_number}
            </T>
            <T>{n.text}</T>
          </Card>
        ))}
      </View>
      <View style={{ gap: Space.sm }}>
        <T variant="heading" accessibilityRole="header">
          Favourite topics
        </T>
        {favourites.length === 0 && <T variant="muted">No favourites yet. Star a topic in any chapter&apos;s topic list.</T>}
        {favourites.map((f) => (
          <Card key={f.topic_id} label={`Favourite topic ${f.title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: f.chapter_id } })}>
            <T style={{ fontWeight: "600" }}>
              {f.number ? `${f.number} ` : ""}
              {f.title}
            </T>
            <T variant="small">
              {GRADE_LABEL[f.grade]} {subject(f.subject)} · Chapter {f.chapter_number}: {f.chapter_title}
            </T>
          </Card>
        ))}
      </View>
      <View style={{ gap: Space.sm }}>
        <T variant="heading" accessibilityRole="header">
          Saved formulas
        </T>
        {formulas.filter((f) => !removed.has(f.id)).length === 0 && <T variant="muted">No formulas yet. Use &quot;Save formula&quot; under a formula in a lesson.</T>}
        {formulas
          .filter((f) => !removed.has(f.id))
          .map((f) => (
            <Card key={f.id}>
              <T>{f.text_alt}</T>
              <T variant="mono">{f.latex}</T>
              {f.updated_since && (
                <Notice tone="warn" title="The lesson has been updated">
                  Check the lesson for the current version of this formula.
                </Notice>
              )}
              <T variant="small">{f.lesson_title}</T>
              <Button
                variant="link"
                label="Remove"
                onPress={async () => {
                  try {
                    await api.removeFormula(token, f.id);
                    setRemoved((r) => new Set(r).add(f.id));
                  } catch {
                    /* stays listed; the learner can try again */
                  }
                }}
              />
            </Card>
          ))}
      </View>
    </View>
  );
}
