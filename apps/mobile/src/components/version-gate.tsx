// P13.S1.T4 (CLIENTS-01): this build asks whether its version is still supported. A minimum announced for later is a
// notice with the date; once it applies, the app explains that it needs updating instead of failing request by request.
import { useEffect, useState, type ReactNode } from "react";
import { ScrollView, View } from "react-native";
import type { ClientPolicy } from "@portal/contracts";

import { Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api, APP_VERSION, SURFACE } from "@/lib/api";
import { TIME_ZONE } from "@/lib/dates";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "long", timeZone: TIME_ZONE });
const STORE = SURFACE === "ios" ? "the App Store" : "Google Play";

export function VersionGate({ children }: { children: ReactNode }) {
  const c = useTheme();
  const [policy, setPolicy] = useState<ClientPolicy | null>(null);
  useEffect(() => {
    if (SURFACE === "web" || !APP_VERSION) return; // the web preview is always current
    api.clientPolicy(SURFACE, APP_VERSION).then(setPolicy, () => undefined); // offline: check again next start
  }, []);
  if (policy?.status === "update_required") {
    return (
      <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: Space.lg, gap: Space.md }}>
        <T variant="title" accessibilityRole="header" style={{ textAlign: "center" }}>
          Please update the app
        </T>
        <T variant="muted" style={{ textAlign: "center" }}>
          This version ({APP_VERSION}) is no longer supported. Update to version {policy.min_version} or later from {STORE} to keep learning. Your progress and
          results are kept on your account.
        </T>
      </ScrollView>
    );
  }
  return (
    <View style={{ flex: 1 }}>
      {policy?.status === "update_soon" && policy.enforce_at ? (
        <View style={{ padding: Space.sm, backgroundColor: c.surface }}>
          <Notice tone="warn" title="An update is needed soon">
            From {day(policy.enforce_at)} this version stops working. Update from {STORE} before then.
          </Notice>
        </View>
      ) : null}
      {children}
    </View>
  );
}
