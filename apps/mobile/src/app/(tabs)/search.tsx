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
import { useAuth } from "@/lib/auth";

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
          accessibilityLabel="Search for"
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

const KIND_LABEL: Record<string, string> = { chapter: "Chapter", topic: "Topic", lesson: "Lesson" };
const LANGUAGE_NAME: Record<string, string> = { ur: "Urdu", roman_ur: "Roman Urdu" };

function Results({ q, grade }: { q: string; grade?: number }) {
  const auth = useAuth();
  if (auth.state.status === "loading") return <Loading label="Searching" />; // wait for the stored session
  return <ResultList q={q} grade={grade} token={auth.state.status === "signed_in" ? auth.state.token : null} />;
}

function ResultList({ q, grade, token }: { q: string; grade?: number; token: string | null }) {
  const c = useTheme();
  const { state, retry } = useRequest((signal) => api.search(q, grade, token, signal), [q, grade, token]);
  if (state.status === "loading") return <Loading label="Searching" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
  const { hits, also_searched: also = [] } = state.data;
  if (hits.length === 0) return <T variant="muted" style={{ padding: Space.lg }}>Nothing matches “{q}”.</T>;
  return (
    <FlatList
      contentContainerStyle={{ paddingHorizontal: Space.lg, paddingBottom: Space.xl, gap: Space.sm }}
      data={hits}
      ListHeaderComponent={also.length > 0 ? <T variant="small">Also searched for {also.join(", ")} (the same term in English, Urdu or Roman Urdu).</T> : null}
      keyExtractor={(h: SearchHit) => `${h.kind}-${h.id}`}
      renderItem={({ item: h }) => {
        const urdu = h.language === "ur";
        const rtl = urdu ? ({ writingDirection: "rtl", textAlign: "right" } as const) : undefined;
        return (
          // The chapter screen checks publication and access again when it opens.
          <Card label={`${GRADE_LABEL[h.grade]} ${h.subject_name}: ${h.title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: h.chapter_id } })}>
            <T variant="eyebrow">
              {GRADE_LABEL[h.grade]} · {h.subject_name} · {KIND_LABEL[h.kind] ?? h.kind}
              {h.kind === "lesson" && h.language && LANGUAGE_NAME[h.language] ? ` (${LANGUAGE_NAME[h.language]})` : ""}
              {h.kind === "lesson" && h.access_tier === "preview" ? " · Free preview" : ""}
            </T>
            <T style={{ fontWeight: "600", ...rtl }}>{h.title}</T>
            {h.kind !== "chapter" && <T variant="small">in {h.chapter_title}</T>}
            {h.locked && <T variant="small">Included with a plan or the free 30-day trial. Found by its title.</T>}
            {!h.locked && (h.snippet ?? []).length > 0 && (
              <T variant="small" style={rtl}>
                {(h.snippet ?? []).map((p, i) =>
                  p.match ? (
                    <T key={i} variant="small" style={{ fontWeight: "700", backgroundColor: c.accentSoft }}>
                      {p.text}
                    </T>
                  ) : (
                    p.text
                  ),
                )}
              </T>
            )}
          </Card>
        );
      }}
    />
  );
}
