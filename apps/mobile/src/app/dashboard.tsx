// The learner dashboard (DASHBOARD-01) on its own screen, so the Learn tab stays about reading. Same figures and
// definitions as the web home; a meter without a verified denominator says why instead of showing a percentage.
import { Stack } from "expo-router";
import { ScrollView } from "react-native";

import { DashboardSection } from "@/components/dashboard";
import { Notice } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { useAuth } from "@/lib/auth";

export default function DashboardScreen() {
  const { state } = useAuth();
  const c = useTheme();
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      <Stack.Screen options={{ title: "Dashboard" }} />
      {state.status === "signed_in" ? <DashboardSection token={state.token} /> : <Notice title="Sign in to see your dashboard">Open the Account tab to sign in.</Notice>}
    </ScrollView>
  );
}
