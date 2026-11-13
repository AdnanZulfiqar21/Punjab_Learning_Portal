import { router } from "expo-router";
import { useEffect, useState } from "react";
import { FlatList, Pressable, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { SearchHit } from "@portal/contracts";

import { Screen } from "@/components/premium";
import { Card, ErrorState, Loading, T } from "@/components/ui";
import { Radius, Space, TAB_SCREEN_TOP } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const GRADES: { value: number | undefined; label: string }[] = [
  { value: undefined, label: "11 + 12" },
  { value: 11, label: "Class 11" },
  { value: 12, label: "Class 12" },
];

export default function SearchScreen() {
  const c = useTheme();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState<number | undefined>(undefined);
  return (
    <Screen>
    <SafeAreaView edges={["top"]} style={{ flex: 1 }}>
      <View style={{ padding: Space.lg, paddingTop: TAB_SCREEN_TOP, gap: Space.md }}>
        <T variant="title">Search</T>
        <TextInput
          accessibilityLabel="Search for"
          placeholder="e.g. photosynthesis, kinetic theory"
          placeholderTextColor={c.muted}
          value={draft}
          onChangeText={setDraft}
          onSubmitEditing={() => setQuery(draft.trim())}
          accessibilityHint="Suggestions appear below as you type"
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
      {draft.trim().length >= 2 && draft.trim() !== query ? (
        <Suggestions typed={draft.trim()} grade={grade} onSearch={() => setQuery(draft.trim())} />
      ) : query.length >= 2 ? (
        <Results q={query} grade={grade} />
      ) : (
        <T variant="muted" style={{ paddingHorizontal: Space.lg }}>Enter at least two characters.</T>
      )}
    </SafeAreaView>
    </Screen>
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

/**
 * SEARCH-SUGGEST-01 (owner, 2026-11-13): while the learner types, the chapters and topics whose titles match, under the
 * box; a tap opens one. "Search" (or the keyboard's search key) runs the full search, lessons included.
 */
function Suggestions({ typed, grade, onSearch }: { typed: string; grade?: number; onSearch: () => void }) {
  const c = useTheme();
  const [q, setQ] = useState(typed);
  useEffect(() => {
    const id = setTimeout(() => setQ(typed), 200);
    return () => clearTimeout(id);
  }, [typed]);
  const { state } = useRequest((signal) => api.suggest(q, grade, signal), [q, grade]);
  const hits = state.status === "success" ? state.data.hits.filter((h) => h.kind === "chapter" || h.kind === "topic") : [];
  const lower = q.toLowerCase();
  return (
    <View style={{ paddingHorizontal: Space.lg, gap: Space.xs }} accessibilityLabel="Suggestions">
      {state.status === "success" && hits.length === 0 ? (
        <T variant="muted">{`No chapter or topic is named like “${q}”.`}</T>
      ) : null}
      {hits.map((h) => {
        const at = h.title.toLowerCase().indexOf(lower);
        return (
          <Pressable
            key={`${h.kind}-${h.id}`}
            accessibilityRole="button"
            accessibilityLabel={`${h.title}. ${GRADE_LABEL[h.grade]} ${h.subject_name} ${h.kind === "chapter" ? "chapter" : "topic"}`}
            onPress={() =>
              h.kind === "topic"
                ? router.push({ pathname: "/topic/[id]", params: { id: h.id } })
                : router.push({ pathname: "/chapter/[id]", params: { id: h.chapter_id } })
            }
            style={({ pressed }) => ({ minHeight: 52, justifyContent: "center", paddingHorizontal: Space.md, paddingVertical: Space.sm, borderRadius: Radius.lg, backgroundColor: pressed ? c.accentSoft : c.surface, borderWidth: 1, borderColor: c.border })}>
            <T style={{ fontWeight: "600" }} numberOfLines={2}>
              {at < 0 ? (
                h.title
              ) : (
                <>
                  {h.title.slice(0, at)}
                  <T style={{ fontWeight: "800", backgroundColor: c.accentSoft }}>{h.title.slice(at, at + q.length)}</T>
                  {h.title.slice(at + q.length)}
                </>
              )}
            </T>
            <T variant="small" numberOfLines={1} style={{ color: c.muted }}>
              {`${GRADE_LABEL[h.grade]} · ${h.subject_name} · ${h.kind === "chapter" ? "Chapter" : `Topic in ${h.chapter_title}`}`}
            </T>
          </Pressable>
        );
      })}
      <Pressable accessibilityRole="button" onPress={onSearch} style={{ minHeight: 48, justifyContent: "center", paddingHorizontal: Space.md }}>
        <T style={{ color: c.accent, fontWeight: "700" }}>{`Search for “${typed}” in lessons too`}</T>
      </Pressable>
    </View>
  );
}
