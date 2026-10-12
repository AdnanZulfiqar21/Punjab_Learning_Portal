// P13.S3 (OFFLINE-PACKS-01): a saved chapter, read and practised without a connection. Practice here is a self-check:
// nothing is sent, saved or scored, and it never counts as a test result (timed and mock tests are never saved).
import { Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { LessonBlocks } from "@/components/lesson-blocks";
import { Card, Notice, T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { useAuth } from "@/lib/auth";
import { packFile, readPack, type PackQuestion } from "@/lib/study-packs";

type Blocks = { type: string }[];

export default function OfflineChapter() {
  const c = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { state } = useAuth();
  const owner = state.status === "signed_in" ? state.me.id : "";
  const pack = owner ? readPack(owner, id) : null;
  const [tab, setTab] = useState<"lessons" | "practice">("lessons");
  if (!pack) {
    return (
      <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg }}>
        <Stack.Screen options={{ title: "Saved copy" }} />
        <Notice tone="warn" title="No saved copy">
          There is no saved copy of this chapter on this device, or it has expired. Save it again when you are online.
        </Notice>
      </ScrollView>
    );
  }
  const asset = (versionId: string) => ({ uri: packFile(owner, id, versionId) ?? "" });
  const passages = new Map(pack.content.passages.map((p) => [p.id, p]));
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: "Saved copy" }} />
      <View accessibilityRole="tablist" style={{ flexDirection: "row", gap: Space.sm }}>
        {(["lessons", "practice"] as const).map((t) => (
          <Pressable
            key={t}
            accessibilityRole="tab"
            accessibilityState={{ selected: tab === t }}
            onPress={() => setTab(t)}
            style={{ paddingVertical: Space.sm, paddingHorizontal: Space.md, borderRadius: Radius.sm, backgroundColor: tab === t ? c.surfaceMuted : "transparent" }}
          >
            <T style={{ fontWeight: tab === t ? "700" : "400" }}>{t === "lessons" ? `Lessons (${pack.content.lessons.length})` : `Practice (${pack.content.questions.length})`}</T>
          </Pressable>
        ))}
      </View>
      {tab === "lessons" ? (
        pack.content.lessons.length === 0 ? (
          <T variant="muted">No lessons were saved for this chapter.</T>
        ) : (
          pack.content.lessons.map((l) => (
            <Card key={l.id}>
              <T variant="heading" accessibilityRole="header">
                {l.title}
              </T>
              <LessonBlocks blocks={l.body.blocks} assetSource={asset} />
            </Card>
          ))
        )
      ) : (
        <>
          <Notice title="Self-check">Choose an answer to see the explanation. Nothing here is sent, saved or scored.</Notice>
          {pack.content.questions.length === 0 ? (
            <T variant="muted">No practice questions were saved for this chapter.</T>
          ) : (
            pack.content.questions.map((q, i) => (
              <Question key={q.id} number={i + 1} q={q} passage={q.body.passage_id ? passages.get(q.body.passage_id)?.body.blocks : undefined} />
            ))
          )}
        </>
      )}
    </ScrollView>
  );
}

function Question({ number, q, passage }: { number: number; q: PackQuestion; passage?: Blocks }) {
  const c = useTheme();
  const [chosen, setChosen] = useState<string | null>(null);
  const none = () => ({ uri: "" });
  return (
    <Card>
      <T variant="small">Question {number}</T>
      {passage ? <LessonBlocks blocks={passage} assetSource={none} /> : null}
      <LessonBlocks blocks={(q.body.stem ?? []) as Blocks} assetSource={none} />
      <View style={{ gap: Space.sm, marginTop: Space.sm }}>
        {(q.body.options ?? []).map((o) => {
          const isKey = o.id === q.body.correct_option_id;
          const border = chosen === null ? c.border : isKey ? c.accent : o.id === chosen ? c.danger : c.border;
          return (
            <Pressable
              key={o.id}
              accessibilityRole="radio"
              accessibilityState={{ checked: chosen === o.id, disabled: chosen !== null }}
              disabled={chosen !== null}
              onPress={() => setChosen(o.id)}
              style={{ borderWidth: 1, borderColor: border, borderRadius: Radius.sm, padding: Space.sm }}
            >
              <LessonBlocks blocks={(o.blocks ?? []) as Blocks} assetSource={none} />
              {chosen !== null && isKey ? <T variant="small">✓ Correct answer</T> : null}
            </Pressable>
          );
        })}
      </View>
      {chosen !== null && (
        <View accessibilityLiveRegion="polite" style={{ marginTop: Space.sm, gap: Space.xs }}>
          <T style={{ fontWeight: "600" }}>{chosen === q.body.correct_option_id ? "Right." : "Not quite."}</T>
          {chosen !== q.body.correct_option_id && q.body.explanation?.distractors?.[chosen] ? <T variant="small">{q.body.explanation.distractors[chosen]}</T> : null}
          <LessonBlocks blocks={(q.body.explanation?.correct ?? []) as Blocks} assetSource={none} />
        </View>
      )}
    </Card>
  );
}
