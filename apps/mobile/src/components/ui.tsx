import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type TextProps, type ViewStyle } from "react-native";

import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import type { ApiError } from "@/lib/api";

type Variant = "title" | "heading" | "body" | "muted" | "small" | "eyebrow" | "mono";

export function T({ variant = "body", style, ...rest }: TextProps & { variant?: Variant }) {
  const c = useTheme();
  const color = variant === "muted" || variant === "small" ? c.muted : variant === "eyebrow" ? c.accent : c.text;
  return <Text style={[{ color }, text[variant], style]} {...rest} />;
}

const text = StyleSheet.create({
  title: { fontSize: 26, lineHeight: 32, fontWeight: "700" },
  heading: { fontSize: 18, lineHeight: 24, fontWeight: "600" },
  body: { fontSize: 16, lineHeight: 23 },
  muted: { fontSize: 15, lineHeight: 22 },
  small: { fontSize: 13, lineHeight: 18 },
  eyebrow: { fontSize: 13, lineHeight: 18, fontWeight: "600" },
  mono: { fontSize: 13, lineHeight: 18, fontFamily: "monospace" },
});

export function Card({ children, onPress, style, label }: { children: ReactNode; onPress?: () => void; style?: ViewStyle; label?: string }) {
  const c = useTheme();
  const base = [styles.card, { backgroundColor: c.surface, borderColor: c.border }, style];
  if (!onPress) return <View style={base}>{children}</View>;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [...base, pressed && { borderColor: c.accent, opacity: 0.85 }]}>
      {children}
    </Pressable>
  );
}

export function Badge({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" }) {
  const c = useTheme();
  return (
    <View style={[styles.badge, { backgroundColor: tone === "warn" ? c.warnSoft : c.accentSoft }]}>
      <Text style={{ color: tone === "warn" ? c.warn : c.accent, fontSize: 12, fontWeight: "600" }}>{children}</Text>
    </View>
  );
}

export function Notice({ title, children, tone = "info" }: { title: string; children?: ReactNode; tone?: "info" | "warn" }) {
  const c = useTheme();
  return (
    <View
      accessibilityRole="summary"
      style={[styles.notice, { backgroundColor: tone === "warn" ? c.warnSoft : c.accentSoft, borderColor: c.border }]}>
      <T style={{ fontWeight: "600" }}>{title}</T>
      {children ? <T variant="muted">{children}</T> : null}
    </View>
  );
}

export function Loading({ label }: { label: string }) {
  const c = useTheme();
  return (
    <View style={styles.center} accessible accessibilityLabel={label} aria-busy>
      <ActivityIndicator color={c.accent} size="large" />
      <T variant="muted" style={{ marginTop: Space.md }}>
        {label}
      </T>
    </View>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  const c = useTheme();
  const title = error.kind === "not_found" ? "This isn’t available" : error.kind === "offline" ? "You’re offline" : "Something went wrong";
  return (
    <View style={styles.center} accessibilityRole="alert">
      <T variant="heading" style={{ textAlign: "center" }}>
        {title}
      </T>
      <T variant="muted" style={{ textAlign: "center", marginTop: Space.sm }}>
        {error.message}
      </T>
      {error.kind !== "not_found" && (
        <Pressable
          accessibilityRole="button"
          onPress={onRetry}
          style={({ pressed }) => [styles.button, { backgroundColor: c.accent, opacity: pressed ? 0.8 : 1 }]}>
          <Text style={{ color: c.onAccent, fontWeight: "600", fontSize: 16 }}>Try again</Text>
        </Pressable>
      )}
      {error.correlationId ? (
        <T variant="small" style={{ marginTop: Space.md }}>
          Reference: {error.correlationId.slice(0, 12)}
        </T>
      ) : null}
    </View>
  );
}

export const styles = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: Radius.md, padding: Space.lg, gap: Space.xs },
  badge: { alignSelf: "flex-start", borderRadius: Radius.pill, paddingHorizontal: Space.sm, paddingVertical: 2 },
  notice: { borderWidth: 1, borderRadius: Radius.md, padding: Space.lg, gap: Space.xs },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: Space.xl },
  button: { marginTop: Space.lg, minHeight: 48, paddingHorizontal: Space.xl, borderRadius: Radius.sm, justifyContent: "center" },
});
