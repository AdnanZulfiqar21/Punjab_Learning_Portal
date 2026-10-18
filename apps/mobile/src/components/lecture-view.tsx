// The Lecture view of a topic (LECTURE-READ-01): the approved lecture's video with its chapter markers and
// transcript, or an honest "coming" state. Playback uses expo-video; the stream is the API's own (development
// media directory until the media provider, B05), sent with the session so premium rules hold.
import { useVideoPlayer, VideoView } from "expo-video";
import { useState } from "react";
import { Pressable, useWindowDimensions, View } from "react-native";

import { Chip, LinkButton, Notice, Segmented, T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { apiUrl, type TopicLecture } from "@/lib/api";

const LANGUAGE: Record<string, string> = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" };
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function LectureView({ data, token }: { data: TopicLecture; token: string | null }) {
  const [part, setPart] = useState(0);
  const lecture = data.lectures[part] ?? data.lectures[0];
  if (data.availability !== "available" || !lecture) {
    return (
      <Notice title="The lecture for this topic is coming">
        Lectures are added topic by topic after an independent academic review. The lesson text below is complete.
      </Notice>
    );
  }
  if (lecture.locked || !lecture.stream_path) {
    return (
      <Notice title="Included with a plan or the free 30-day trial">
        {token ? "Start your free trial from the Account tab to watch this lecture." : "Sign in from the Account tab, then start your free trial to watch this lecture."}
      </Notice>
    );
  }
  return (
    <View style={{ gap: Space.sm }}>
      {data.lectures.length > 1 && (
        <Segmented
          label="Lecture part"
          options={data.lectures.map((l, i) => [String(i), `Part ${i + 1}`] as const)}
          value={String(data.lectures.indexOf(lecture))}
          onChange={(v) => setPart(Number(v))}
        />
      )}
      <Player key={lecture.id} uri={apiUrl(lecture.stream_path)} token={token} lecture={lecture} />
    </View>
  );
}

function Player({ uri, token, lecture }: { uri: string; token: string | null; lecture: TopicLecture["lectures"][number] }) {
  const c = useTheme();
  const { width } = useWindowDimensions();
  // The pilot's lectures are portrait (9:16): give the player the height a portrait video needs, capped so the
  // markers stay in reach; a landscape video simply letterboxes inside it.
  const height = Math.min(Math.round(((width - 2 * Space.lg) * 16) / 9), 600);
  const [showTranscript, setShowTranscript] = useState(false);
  const player = useVideoPlayer({ uri, headers: token ? { Authorization: `Bearer ${token}` } : undefined }, (p) => {
    p.timeUpdateEventInterval = 1;
  });
  return (
    <View style={{ gap: Space.sm }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flexWrap: "wrap" }}>
        <Chip label={`Lecture in ${LANGUAGE[lecture.language] ?? lecture.language}`}>{LANGUAGE[lecture.language] ?? lecture.language}</Chip>
        <T variant="small" style={{ flex: 1 }}>
          {lecture.title} · {mmss(lecture.duration_s)}
        </T>
      </View>
      <View style={{ borderRadius: Radius.md, overflow: "hidden", backgroundColor: "#000000" }}>
        <VideoView player={player} style={{ width: "100%", height }} contentFit="contain" nativeControls fullscreenOptions={{ enable: true }} accessibilityLabel={lecture.title} />
      </View>
      {lecture.markers.length > 0 && (
        <View style={{ gap: Space.xs }}>
          <T variant="eyebrow">In this lecture</T>
          {lecture.markers.map((m) => (
            <Pressable
              key={m.scene_id}
              accessibilityRole="button"
              accessibilityLabel={`Go to ${m.label}, ${mmss(m.start_s)}`}
              onPress={() => {
                player.currentTime = m.start_s;
                player.play();
              }}
              style={({ pressed }) => ({ flexDirection: "row", gap: Space.sm, minHeight: 44, alignItems: "center", opacity: pressed ? 0.7 : 1 })}>
              <T variant="mono" style={{ color: c.accent, width: 44 }}>
                {mmss(m.start_s)}
              </T>
              <T style={{ flex: 1 }}>{m.label}</T>
            </Pressable>
          ))}
        </View>
      )}
      {lecture.transcript.length > 0 && (
        <View style={{ gap: Space.xs }}>
          <LinkButton label={showTranscript ? "Hide the transcript" : "Read the transcript"} onPress={() => setShowTranscript((s) => !s)} />
          {showTranscript
            ? lecture.transcript.map((t) => (
                <T key={t.scene_id} variant="muted">
                  {t.text}
                </T>
              ))
            : null}
        </View>
      )}
    </View>
  );
}
