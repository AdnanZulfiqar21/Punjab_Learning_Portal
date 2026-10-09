// Notifications on native (P15.S1): the same inbox as the web. Opening one marks it read and goes to the screen it
// points to. Push delivery to this device needs installable builds and push credentials (BLOCKERS B07); until then
// notices arrive here and by email.
import { router, Stack } from "expo-router";
import { Pressable, ScrollView, View } from "react-native";
import type { InboxItem } from "@portal/contracts";

import { Button } from "@/components/form";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

/** Web paths in notifications → the matching native screen. Unknown paths stay on this screen. */
function route(link: string | null): void {
  const written = link?.match(/^\/practice\/written\/([0-9a-f-]{36})$/i);
  if (written) return void router.push({ pathname: "/written/[id]", params: { id: written[1] } });
  if (link?.startsWith("/help")) return void router.push("/help");
  if (link === "/account") return void router.navigate("/account");
}

export default function NotificationsScreen() {
  const { state } = useAuth();
  const c = useTheme();
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      <Stack.Screen options={{ title: "Notifications" }} />
      {state.status === "loading" && <Loading label="Checking your sign-in" />}
      {state.status !== "loading" && state.status !== "signed_in" && <Notice title="Sign in to see notifications">Open the Account tab to sign in.</Notice>}
      {state.status === "signed_in" && <Inbox token={state.token} />}
    </ScrollView>
  );
}

function Inbox({ token }: { token: string }) {
  const req = useRequest((signal) => api.notifications(token, signal), [token]);
  if (req.state.status === "loading") return <Loading label="Loading notifications" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const { items, unread } = req.state.data;
  async function open(n: InboxItem) {
    if (!n.read_at) await api.readNotification(token, n.id).catch(() => undefined);
    req.retry();
    route(n.link);
  }
  return (
    <View style={{ gap: Space.md }}>
      <T variant="small" accessibilityRole="text">
        {unread} unread
      </T>
      {unread > 0 && (
        <Button
          variant="secondary"
          label="Mark all as read"
          onPress={async () => {
            await api.readAllNotifications(token).catch(() => undefined);
            req.retry();
          }}
        />
      )}
      {items.length === 0 && <Notice title="Nothing yet">Marks, requests from teachers and replies to your help requests appear here.</Notice>}
      {items.map((n) => (
        <Pressable key={n.id} accessibilityRole="button" accessibilityLabel={n.title} onPress={() => void open(n)}>
          <Card>
            <View style={{ gap: Space.xs }}>
              <T style={{ fontWeight: n.read_at ? "400" : "700" }}>
                {n.read_at ? "" : "● "}
                {n.title}
              </T>
              <T variant="small">{n.body}</T>
              <T variant="small">{when(n.created_at)}</T>
            </View>
          </Card>
        </Pressable>
      ))}
    </View>
  );
}
