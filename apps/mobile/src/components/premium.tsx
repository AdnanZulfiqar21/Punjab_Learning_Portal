// PREMIUM-MOBILE-01 (owner, 2026-11-08: "mobile pr bhe premium banao"): the web portal's Soft Glass look (DESIGN-01,
// PREMIUM-LOOK-01) on the phone. A gradient mesh behind the browsing screens, subject icon tiles and the subject's
// gradient banner over chapter and lesson titles. Everything is drawn by the native view (CSS gradients), with no
// images, no live blur and no animation library, so it costs nothing measurable on a low-end phone. Lesson text itself
// never sits on the mesh (owner rule): the lesson screens keep their solid background.
import { SymbolView } from "expo-symbols";
import type { ReactNode } from "react";
import { Platform, StyleSheet, Text, View, type ViewStyle } from "react-native";

import { bannerStops, Glass, HeadingFont, Radius, Space, SubjectAccents, SubjectSymbol, subjectKey } from "@/constants/theme";
import { useScheme, useTheme } from "@/hooks/use-theme";

/** A CSS gradient as a view background: native views take `experimental_backgroundImage`, the web target CSS. */
export function gradient(css: string): ViewStyle {
  return (Platform.OS === "web" ? { backgroundImage: css } : { experimental_backgroundImage: css }) as ViewStyle;
}

/** The same colour fully transparent, so a gradient fades without a grey fringe. */
function clear(color: string): string {
  if (color.startsWith("#")) return `${color.slice(0, 7)}00`;
  return color.replace(/,\s*[\d.]+\)$/, ",0)");
}

/** The soft teal, lavender and peach mesh fixed behind a screen (light; faint in dark). */
export function Mesh() {
  const scheme = useScheme();
  const [a, b, c] = Glass[scheme].mesh;
  const css =
    `radial-gradient(circle at 8% 0%, ${a} 0%, ${clear(a)} 55%), ` +
    `radial-gradient(circle at 100% 6%, ${b} 0%, ${clear(b)} 50%), ` +
    `radial-gradient(circle at 50% 100%, ${c} 0%, ${clear(c)} 55%)`;
  return <View pointerEvents="none" style={[StyleSheet.absoluteFill, gradient(css)]} />;
}

/** A browsing screen: the page colour with the mesh behind its content. */
export function Screen({ children }: { children: ReactNode }) {
  const c = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: c.background }}>
      <Mesh />
      {children}
    </View>
  );
}

/** A subject's rounded icon tile in its own accent gradient (web subject tiles). */
export function SubjectTile({ subject, size = 48 }: { subject: string | null | undefined; size?: number }) {
  const scheme = useScheme();
  const key = subjectKey(subject);
  const [from, to] = bannerStops(key, "light");
  const symbol = key ? SubjectSymbol[key] : null;
  const initials = symbol?.initials ?? (subject ?? "").slice(0, 2);
  const fallback = <Text style={{ color: "#ffffff", fontFamily: HeadingFont.bold, fontSize: size * 0.36 }}>{initials}</Text>;
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        { width: size, height: size, borderRadius: size * 0.3, alignItems: "center", justifyContent: "center", opacity: scheme === "dark" ? 0.92 : 1 },
        gradient(`linear-gradient(135deg, ${from}, ${to})`),
      ]}>
      {symbol && Platform.OS === "ios" ? (
        <SymbolView name={symbol.ios as never} tintColor="#ffffff" size={size * 0.5} fallback={fallback} />
      ) : (
        fallback
      )}
    </View>
  );
}

/** The subject's gradient banner over a chapter or lesson title (web chapter and topic headers). White text on it. */
export function Banner({ subject, children, style }: { subject: string | null | undefined; children: ReactNode; style?: ViewStyle }) {
  const scheme = useScheme();
  const [from, to] = bannerStops(subjectKey(subject), scheme);
  return (
    <View
      style={[
        { borderRadius: Radius.xl + 4, padding: Space.xl, gap: Space.sm, overflow: "hidden", boxShadow: Glass[scheme].shadow },
        gradient(`linear-gradient(135deg, ${from}, ${to})`),
        style,
      ]}>
      {/* a soft light in the top corner, as on the web banner */}
      <View
        pointerEvents="none"
        style={[StyleSheet.absoluteFill, gradient("radial-gradient(circle at 100% 0%, rgba(255,255,255,0.22) 0%, rgba(255,255,255,0) 45%)")]}
      />
      {children}
    </View>
  );
}

/** Text on a banner: an eyebrow line, the title, and a quieter line under it. */
export function BannerText({ variant, children, numberOfLines }: { variant: "eyebrow" | "title" | "body"; children: ReactNode; numberOfLines?: number }) {
  const style =
    variant === "eyebrow"
      ? { fontSize: 13, lineHeight: 18, fontWeight: "600" as const, color: "rgba(255,255,255,0.85)", letterSpacing: 0.3 }
      : variant === "title"
        ? { fontSize: 28, lineHeight: 34, fontFamily: HeadingFont.bold, color: "#ffffff", letterSpacing: -0.3 }
        : { fontSize: 15, lineHeight: 22, color: "rgba(255,255,255,0.9)" };
  return (
    <Text style={style} numberOfLines={numberOfLines} accessibilityRole={variant === "title" ? "header" : undefined}>
      {children}
    </Text>
  );
}

/** A subject's accent for its card edge and icon (the portal's teal when the subject is unknown). */
export function useSubjectAccent(subject: string | null | undefined): string {
  const scheme = useScheme();
  const c = useTheme();
  const key = subjectKey(subject);
  return key ? SubjectAccents[key][scheme].accent : c.accent;
}
