import { router } from "expo-router";
import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type TextProps, type ViewStyle } from "react-native";

import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import type { ApiError } from "@/lib/api";
import { useDisplay } from "@/lib/display-context";

type Variant = "title" | "heading" | "subheading" | "body" | "muted" | "small" | "eyebrow" | "mono";

export function T({ variant = "body", style, ...rest }: TextProps & { variant?: Variant }) {
  const c = useTheme();
  const { scale } = useDisplay(); // SETTINGS-01: larger text on this device; the system text size still applies on top
  const color = variant === "muted" || variant === "small" ? c.muted : variant === "eyebrow" ? c.accent : c.text;
  const v = text[variant];
  const sized = scale === 1 ? v : { ...v, fontSize: v.fontSize * scale, lineHeight: v.lineHeight * scale };
  return <Text style={[{ color }, sized, style]} {...rest} />;
}

// Reading sizes: 16/24 body for long lessons, a clear step between title, section and sub-section.
const text = StyleSheet.create({
  title: { fontSize: 27, lineHeight: 33, fontWeight: "700", letterSpacing: -0.3 },
  heading: { fontSize: 20, lineHeight: 26, fontWeight: "700" },
  subheading: { fontSize: 17, lineHeight: 24, fontWeight: "600" },
  body: { fontSize: 16, lineHeight: 24 },
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

/** A small, quiet status chip ("Draft preview", "3D model"): outlined, never a panel. */
export function Chip({ children, label }: { children: string; label?: string }) {
  const c = useTheme();
  return (
    <View accessibilityLabel={label ?? children} style={[styles.chip, { borderColor: c.border, backgroundColor: c.surfaceMuted }]}>
      <Text style={{ color: c.muted, fontSize: 12, fontWeight: "600" }}>{children}</Text>
    </View>
  );
}

/** Two or three exclusive options side by side (e.g. the reader language). Radio semantics for screen readers. */
export function Segmented<V extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly (readonly [V, string])[];
  value: V;
  onChange: (value: V) => void;
}) {
  const c = useTheme();
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={label} style={[styles.segmented, { borderColor: c.border, backgroundColor: c.surfaceMuted }]}>
      {options.map(([v, text]) => {
        const on = v === value;
        return (
          <Pressable
            key={v}
            accessibilityRole="radio"
            aria-checked={on}
            accessibilityLabel={text}
            onPress={() => onChange(v)}
            style={[styles.segment, on && { backgroundColor: c.surface, borderColor: c.border }]}>
            <Text style={{ color: on ? c.text : c.muted, fontSize: 15, fontWeight: on ? "700" : "500" }}>{text}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** A quiet text action ("Change", "Save for offline") with a 44pt touch target. */
export function LinkButton({ label, onPress, accessibilityLabel, busy }: { label: string; onPress: () => void; accessibilityLabel?: string; busy?: boolean }) {
  const c = useTheme();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={accessibilityLabel ?? label} aria-busy={!!busy} disabled={!!busy} onPress={onPress} style={styles.link}>
      {busy ? <ActivityIndicator color={c.accent} size="small" /> : null}
      <Text style={{ color: c.accent, fontSize: 15, fontWeight: "600" }}>{label}</Text>
    </Pressable>
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
      {error.kind !== "not_found" ? (
        <Pressable
          accessibilityRole="button"
          onPress={onRetry}
          style={({ pressed }) => [styles.button, { backgroundColor: c.accent, opacity: pressed ? 0.8 : 1 }]}>
          <Text style={{ color: c.onAccent, fontWeight: "600", fontSize: 16 }}>Try again</Text>
        </Pressable>
      ) : (
        // P13.S2.T3: retired, locked or missing content (an old link, a notice) still leads somewhere useful.
        <Pressable
          accessibilityRole="button"
          onPress={() => router.navigate("/")}
          style={({ pressed }) => [styles.button, { backgroundColor: c.accent, opacity: pressed ? 0.8 : 1 }]}>
          <Text style={{ color: c.onAccent, fontWeight: "600", fontSize: 16 }}>Go to Learn</Text>
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
  chip: { alignSelf: "flex-start", borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Space.sm, paddingVertical: 3 },
  segmented: { flexDirection: "row", borderWidth: 1, borderRadius: Radius.sm + 2, padding: 3, gap: 3 },
  segment: { flex: 1, minHeight: 40, alignItems: "center", justifyContent: "center", borderRadius: Radius.sm, borderWidth: 1, borderColor: "transparent" },
  link: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: Space.sm, paddingHorizontal: Space.xs },
  notice: { borderWidth: 1, borderRadius: Radius.md, padding: Space.lg, gap: Space.xs },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: Space.xl },
  button: { marginTop: Space.lg, minHeight: 48, paddingHorizontal: Space.xl, borderRadius: Radius.sm, justifyContent: "center" },
});
