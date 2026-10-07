import { router } from "expo-router";
import { useState } from "react";
import { FlatList, Pressable, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { SearchHit } from "@portal/contracts";

import { Card, ErrorState, Loading, T } from "@/components/ui";
import { Radius, Space, TAB_SCREEN_TOP } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";

const GRADES: { value: number | undefined; label: string }[] = [
  { value: undefined, label: "XI + XII" },
  { value: 11, label: "Class XI" },
  { value: 12, label: "Class XII" },
];

export default function SearchScreen() {
  const c = useTheme();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState<number | undefined>(undefined);
  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: c.background }}>
      <View style={{ padding: Space.lg, paddingTop: TAB_SCREEN_TOP, gap: Space.md }}>
        <T variant="title">Search</T>
        <TextInput
          accessibilityLabel="Topic or chapter"
          placeholder="e.g. photosynthesis, kinetic theory"
          placeholderTextColor={c.muted}
          value={draft}
          onChangeText={setDraft}
          onSubmitEditing={() => setQuery(draft.trim())}
          returnKeyType="search"
          autoCorrect={false}
          style={{ borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, color: c.text, borderRadius: Radius.sm, padding: Space.md, fontSize: 16, minHeight: 48 }}
        />
        <View style={{ flexDirection: "row", gap: Space.sm }} accessibilityRole="radiogroup">
          {GRADES.map((g) => {
            const selected = g.value === grade;
            return (
              <Pressable
                key={g.label}
                accessibilityRole="radio"
                aria-checked={selected}
                onPress={() => setGrade(g.value)}
                style={{ borderWidth: 1, borderColor: selected ? c.accent : c.border, backgroundColor: selected ? c.accentSoft : c.surface, borderRadius: Radius.pill, paddingHorizontal: Space.md, minHeight: 40, justifyContent: "center" }}>
                <T variant="small" style={{ color: selected ? c.accent : c.text }}>
                  {g.label}
                </T>
              </Pressable>
            );
          })}
        </View>
      </View>
      {query.length >= 2 ? <Results q={query} grade={grade} /> : <T variant="muted" style={{ paddingHorizontal: Space.lg }}>Enter at least two characters.</T>}
    </SafeAreaView>
  );
}

function Results({ q, grade }: { q: string; grade?: number }) {
  const { state, retry } = useRequest((signal) => api.search(q, grade, signal), [q, grade]);
  if (state.status === "loading") return <Loading label="Searching" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
  const hits = state.data.hits;
  if (hits.length === 0) return <T variant="muted" style={{ padding: Space.lg }}>No chapters or topics match “{q}”.</T>;
  return (
    <FlatList
      contentContainerStyle={{ paddingHorizontal: Space.lg, paddingBottom: Space.xl, gap: Space.sm }}
      data={hits}
      keyExtractor={(h: SearchHit) => `${h.kind}-${h.id}`}
      renderItem={({ item: h }) => (
        <Card label={`${GRADE_LABEL[h.grade]} ${h.subject_name}: ${h.title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: h.chapter_id } })}>
          <T variant="eyebrow">
            {GRADE_LABEL[h.grade]} · {h.subject_name} · {h.kind === "chapter" ? "Chapter" : "Topic"}
          </T>
          <T style={{ fontWeight: "600" }}>{h.title}</T>
          {h.kind === "topic" && <T variant="small">in {h.chapter_title}</T>}
        </Card>
      )}
    />
  );
}
