import { ActivityIndicator, Pressable, Text, TextInput, View, type TextInputProps } from "react-native";

import { T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

export function Field({ label, error, ...input }: TextInputProps & { label: string; error?: string }) {
  const c = useTheme();
  return (
    <View style={{ gap: Space.xs }}>
      <T style={{ fontWeight: "600" }}>{label}</T>
      <TextInput
        accessibilityLabel={label}
        aria-invalid={!!error}
        placeholderTextColor={c.muted}
        style={{
          borderWidth: 1,
          borderColor: error ? c.danger : c.border,
          backgroundColor: c.surface,
          color: c.text,
          borderRadius: Radius.sm,
          padding: Space.md,
          fontSize: 16,
          minHeight: 48,
        }}
        {...input}
      />
      {error ? (
        <T variant="small" style={{ color: c.danger }} accessibilityLiveRegion="polite">
          {error}
        </T>
      ) : null}
    </View>
  );
}

export function Button({
  label,
  onPress,
  busy,
  variant = "primary",
  disabled,
}: {
  label: string;
  onPress: () => void;
  busy?: boolean;
  variant?: "primary" | "secondary" | "link";
  disabled?: boolean;
}) {
  const c = useTheme();
  const inactive = busy || disabled;
  if (variant === "link") {
    return (
      <Pressable accessibilityRole="button" onPress={onPress} disabled={inactive} style={{ minHeight: 44, justifyContent: "center" }}>
        <Text style={{ color: c.accent, fontSize: 15, fontWeight: "600", textAlign: "center" }}>{label}</Text>
      </Pressable>
    );
  }
  const primary = variant === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ busy: !!busy, disabled: !!inactive }}
      onPress={onPress}
      disabled={inactive}
      style={({ pressed }) => ({
        minHeight: 48,
        borderRadius: Radius.sm,
        paddingHorizontal: Space.xl,
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "row",
        gap: Space.sm,
        backgroundColor: primary ? c.accent : c.surface,
        borderWidth: primary ? 0 : 1,
        borderColor: c.border,
        opacity: inactive ? 0.6 : pressed ? 0.85 : 1,
      })}>
      {busy ? <ActivityIndicator color={primary ? c.onAccent : c.accent} /> : null}
      <Text style={{ color: primary ? c.onAccent : c.text, fontWeight: "600", fontSize: 16 }}>{label}</Text>
    </Pressable>
  );
}

/** Single- or multi-select chips with radio/checkbox semantics for screen readers. */
export function Choices<V extends string | number>({
  label,
  options,
  selected,
  onToggle,
  multiple,
}: {
  label: string;
  options: readonly (readonly [V, string])[];
  selected: readonly V[];
  onToggle: (value: V) => void;
  multiple?: boolean;
}) {
  const c = useTheme();
  return (
    <View style={{ gap: Space.xs }}>
      <T style={{ fontWeight: "600" }}>{label}</T>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.sm }} accessibilityRole={multiple ? undefined : "radiogroup"}>
        {options.map(([value, text]) => {
          const on = selected.includes(value);
          return (
            <Pressable
              key={String(value)}
              accessibilityRole={multiple ? "checkbox" : "radio"}
              accessibilityState={{ checked: on }}
              accessibilityLabel={text}
              onPress={() => onToggle(value)}
              style={{
                borderWidth: 1,
                borderColor: on ? c.accent : c.border,
                backgroundColor: on ? c.accentSoft : c.surface,
                borderRadius: Radius.pill,
                paddingHorizontal: Space.lg,
                minHeight: 44,
                justifyContent: "center",
              }}>
              <Text style={{ color: on ? c.accent : c.text, fontSize: 15, fontWeight: on ? "600" : "400" }}>{text}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export function FormError({ message }: { message?: string | null }) {
  const c = useTheme();
  if (!message) return null;
  return (
    <View
      accessibilityRole="alert"
      style={{ borderWidth: 1, borderColor: c.danger, backgroundColor: c.dangerSoft, borderRadius: Radius.sm, padding: Space.md }}>
      <T>{message}</T>
    </View>
  );
}
