// Choose class, then study group (pilot). Two separate questions: a group never implies a class, and Class 11 and
// Class 12 books are never mixed. The ICS note comes from the API's track list, which also decides which books the
// group actually shows.
import { View } from "react-native";

import { Choices } from "@/components/form";
import { Card, LinkButton, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { GRADES, STREAMS, type LearnContext } from "@/lib/learn-context-core";

export function LearnContextPicker({
  value,
  tracks,
  onChange,
  onCancel,
  saving,
}: {
  value: Partial<LearnContext>;
  /** The API's tracks (name, subjects, note), when loaded; used for the note under the group. */
  tracks?: { code: string; subjects: string[]; note: string }[];
  onChange: (next: Partial<LearnContext>) => void;
  onCancel?: () => void;
  saving?: "profile" | "device" | null;
}) {
  const note = tracks?.find((t) => t.code === value.stream)?.note;
  return (
    <Card>
      <View style={{ gap: Space.lg }}>
        <View style={{ gap: Space.xs }}>
          <T variant="heading" accessibilityRole="header">
            What are you studying?
          </T>
          <T variant="small">Class 11 and Class 12 use different textbooks, so choose both.</T>
        </View>
        <Choices label="1. Your class" options={GRADES} selected={value.grade ? [value.grade] : []} onToggle={(grade) => onChange({ ...value, grade })} />
        <View style={{ gap: Space.xs }}>
          <Choices
            label="2. Your study group"
            options={STREAMS.map(([code, name]) => [code, name] as const)}
            selected={value.stream ? [value.stream] : []}
            onToggle={(stream) => onChange({ ...value, stream })}
          />
          <T variant="small">{value.stream ? STREAMS.find(([code]) => code === value.stream)?.[2] : "Pre-Medical, Pre-Engineering or ICS."}</T>
          {note ? <T variant="small">{note}</T> : null}
        </View>
        {saving === "profile" ? (
          <T variant="small">Saved to your profile.</T>
        ) : saving === "device" ? (
          <T variant="small">Kept on this device. Sign in to keep it with your account.</T>
        ) : null}
        {onCancel ? <LinkButton label="Cancel" onPress={onCancel} /> : null}
      </View>
    </Card>
  );
}
