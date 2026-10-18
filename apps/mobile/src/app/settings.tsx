// P04.S3.T2 (SETTINGS-01): display settings for this device, the account's usual settings, and video quality.
import Constants from "expo-constants";
import { useState } from "react";
import { ScrollView, Switch, View } from "react-native";
import type { StudySettings } from "@portal/contracts";

import { Button, Choices, Field, FormError } from "@/components/form";
import { Card, ErrorState, Loading, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, currentApiOrigin } from "@/lib/api";
import { apiOriginOverride, canOverrideApiOrigin, normaliseOrigin, setApiOriginOverride } from "@/lib/api-origin";
import { useAuth } from "@/lib/auth";
import { useDisplay, type TextSize, type Theme } from "@/lib/display";

const THEMES: readonly (readonly [Theme, string])[] = [
  ["system", "Same as this device"],
  ["light", "Light"],
  ["dark", "Dark"],
];
const SIZES: readonly (readonly [TextSize, string])[] = [
  ["default", "Standard"],
  ["large", "Large"],
  ["larger", "Larger"],
];
const VIDEO: readonly (readonly [StudySettings["video_quality"], string])[] = [
  ["auto", "Automatic"],
  ["data_saver", "Data saver"],
  ["standard", "Standard"],
  ["high", "High"],
];

export default function SettingsScreen() {
  const auth = useAuth();
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  return (
    <ScrollView contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <DeviceSettings />
      <PreviewIdentity />
      {token && <UsualSettings token={token} />}
    </ScrollView>
  );
}

function Toggle({ label, hint, value, onChange }: { label: string; hint: string; value: boolean; onChange: (v: boolean) => void }) {
  const c = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: Space.md }}>
      <View style={{ flex: 1 }}>
        <T style={{ fontWeight: "600" }}>{label}</T>
        <T variant="small">{hint}</T>
      </View>
      <Switch accessibilityLabel={label} value={value} onValueChange={onChange} trackColor={{ true: c.accent, false: c.border }} />
    </View>
  );
}

function textExtra(key: string): string | null {
  const value = Constants.expoConfig?.extra?.[key];
  return typeof value === "string" && value ? value : null;
}

/** Preview builds only. Shows which binary this is and which API it calls. No tokens or passwords. */
function PreviewIdentity() {
  const variant = textExtra("variant");
  if (variant === "production") return null;
  const revision = textExtra("sourceRevision");
  return (
    <Card>
      <View style={{ gap: Space.xs }}>
        <T variant="heading" accessibilityRole="header">
          This installation
        </T>
        <T variant="small">Standalone preview. This app does not download a newer version by itself.</T>
        <T variant="small">{`Variant ${variant ?? "unknown"}`}</T>
        <T variant="small">
          {`Version ${Constants.expoConfig?.version ?? "unknown"} (${Constants.nativeBuildVersion ?? Constants.expoConfig?.ios?.buildNumber ?? "unknown"})`}
        </T>
        <T variant="small">{`Source ${revision ? revision.slice(0, 12) : "unknown"}`}</T>
        <T variant="small">{`API ${textExtra("apiOrigin") ?? "not set"}`}</T>
        <ApiAddress />
      </View>
    </Card>
  );
}

/** Preview and development builds: point this device at the laptop's current address without a new build. */
function ApiAddress() {
  const [value, setValue] = useState(apiOriginOverride() ?? "");
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!canOverrideApiOrigin()) return null;
  async function save() {
    setError(null);
    if (value.trim() && !normaliseOrigin(value)) return setError("Use the form http://192.168.1.10:8100 (no path).");
    await setApiOriginOverride(value.trim() || null);
    setSaved(value.trim() ? `Using ${normaliseOrigin(value)} on this device. Restart the app if a screen is still loading.` : "Using the built-in address again.");
  }
  return (
    <View style={{ gap: Space.sm, marginTop: Space.sm }}>
      <Field label="API address on this device" value={value} onChangeText={setValue} autoCapitalize="none" autoCorrect={false} keyboardType="url" placeholder="http://192.168.1.10:8100" error={error ?? undefined} />
      <T variant="small">{`In use now: ${currentApiOrigin()}. Leave empty to use the built-in address.`}</T>
      <Button variant="secondary" label="Save API address" onPress={() => void save()} />
      {saved ? <T variant="small" accessibilityLiveRegion="polite">{saved}</T> : null}
    </View>
  );
}

function DeviceSettings() {
  const { display, change } = useDisplay();
  return (
    <Card>
      <View style={{ gap: Space.md }}>
        <T variant="heading" accessibilityRole="header">
          On this device
        </T>
        <Choices label="Theme" options={THEMES} selected={[display.theme]} onToggle={(theme) => change({ theme })} />
        <Choices label="Text size" options={SIZES} selected={[display.textSize]} onToggle={(textSize) => change({ textSize })} />
        <Toggle
          label="Reduce motion"
          hint="If your device is set to reduce motion, that always applies too."
          value={display.reduceMotion}
          onChange={(reduceMotion) => change({ reduceMotion })}
        />
        <Toggle label="Data saver" hint="Lesson diagrams load only when you tap them." value={display.dataSaver} onChange={(dataSaver) => change({ dataSaver })} />
        <T variant="muted">
          {display.own
            ? "This device keeps its own display settings, even when you change them on another device."
            : "This device uses your usual settings."}
        </T>
      </View>
    </Card>
  );
}

function UsualSettings({ token }: { token: string }) {
  const { display, follow } = useDisplay();
  const req = useRequest((signal) => api.settings(token, signal), [token]);
  const [saved, setSaved] = useState<StudySettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  if (req.state.status === "loading") return <Loading label="Loading your usual settings" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const usual = saved ?? req.state.data;

  async function save(patch: Parameters<typeof api.saveSettings>[1], done: string) {
    setBusy(true);
    try {
      setSaved(await api.saveSettings(token, patch));
      setMessage({ ok: true, text: done });
    } catch {
      setMessage({ ok: false, text: "Couldn't save your settings. Check your connection and try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <View style={{ gap: Space.md }}>
        <T variant="heading" accessibilityRole="header">
          Your usual settings
        </T>
        <T variant="muted">Saved with your account. Devices without their own display settings use them when you sign in.</T>
        <Button
          variant="secondary"
          label="Save this device's settings as my usual settings"
          busy={busy}
          onPress={() =>
            save(
              { theme: display.theme, text_size: display.textSize, reduce_motion: display.reduceMotion, data_saver: display.dataSaver },
              "Saved as your usual settings.",
            )
          }
        />
        {display.own && usual.saved && <Button variant="secondary" label="Use my usual settings here" onPress={() => follow(usual)} />}
        <Choices
          label="Lecture video quality"
          options={VIDEO}
          selected={[usual.video_quality]}
          onToggle={(video_quality) => save({ video_quality }, "Video quality saved.")}
        />
        <T variant="small">Used on all your devices once lecture videos are available.</T>
        {message && (message.ok ? <T accessibilityLiveRegion="polite">{message.text}</T> : <FormError message={message.text} />)}
      </View>
    </Card>
  );
}
