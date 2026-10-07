import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { AppSession, Me } from "@portal/contracts";

import { Button, Field, FormError } from "@/components/form";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space, TAB_SCREEN_TOP } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AccountScreen() {
  const c = useTheme();
  const { state, refresh } = useAuth();
  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: c.background }}>
      {state.status === "loading" && <Loading label="Checking your sign-in" />}
      {state.status === "unavailable" && <ErrorState error={state.error} onRetry={() => void refresh()} />}
      {(state.status === "signed_out" || state.status === "signed_in") && (
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: Space.lg, paddingTop: TAB_SCREEN_TOP, gap: Space.xl }}>
          <T variant="title">Account</T>
          {state.status === "signed_out" ? <SignIn /> : <SignedIn token={state.token} me={state.me} />}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

function SignIn() {
  const methods = useRequest((signal) => api.runtimeConfig(signal), []);
  if (methods.state.status === "loading") return <Loading label="Loading sign-in options" />;
  if (methods.state.status === "error") return <ErrorState error={methods.state.error} onRetry={methods.retry} />;
  const available = methods.state.data.sign_in_methods;
  if (available.includes("dev_password")) return <DevPasswordForm />;
  if (available.includes("oidc")) {
    return (
      <Notice title="Sign-in provider not yet connected">
        This environment uses a managed identity provider, but the in-app sign-in flow is not enabled yet.
      </Notice>
    );
  }
  return <Notice tone="warn" title="Sign-in is not available in this environment" />;
}

function DevPasswordForm() {
  const { signIn, register } = useAuth();
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | undefined>();

  async function submit() {
    setError(null);
    setPasswordError(undefined);
    if (!email.trim() || !password) return setError("Enter your email and password.");
    if (mode === "register" && password.length < 10) return setPasswordError("Use at least 10 characters.");
    setBusy(true);
    try {
      await (mode === "signin" ? signIn : register)(email.trim(), password);
    } catch (e) {
      const kind = e instanceof ApiError ? e.kind : "server";
      setError(
        kind === "unauthorized"
          ? "Email or password is incorrect."
          : kind === "invalid"
            ? "Enter a valid email address."
            : kind === "offline"
              ? "Can't reach the learning service. Check your connection and try again."
              : "Sign-in is unavailable right now.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: Space.lg }}>
      <Notice tone="warn" title="Development sign-in">
        This build uses a local development identity service. Real accounts will sign in through the managed identity
        provider.
      </Notice>
      <Field
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        textContentType="username"
      />
      <Field
        label="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoComplete={mode === "signin" ? "current-password" : "new-password"}
        textContentType={mode === "signin" ? "password" : "newPassword"}
        error={passwordError}
        onSubmitEditing={submit}
      />
      <FormError message={error} />
      <Button label={mode === "signin" ? "Sign in" : "Create account"} onPress={submit} busy={busy} />
      <Button
        variant="link"
        label={mode === "signin" ? "New here? Create an account" : "Already have an account? Sign in"}
        onPress={() => setMode(mode === "signin" ? "register" : "signin")}
      />
    </View>
  );
}

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

function SignedIn({ token, me }: { token: string; me: Me }) {
  const c = useTheme();
  const { signOut, handleError } = useAuth();
  const sessions = useRequest((signal) => api.sessions(token, signal), [token]);
  const [busy, setBusy] = useState<string | null>(null);
  const p = me.profile;

  async function act(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    try {
      await fn();
      sessions.retry();
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(null);
    }
  }

  const sessionsError = sessions.state.status === "error" ? sessions.state.error : null;
  useEffect(() => {
    if (sessionsError) handleError(sessionsError); // a revoked/expired session returns the learner to sign-in
  }, [sessionsError, handleError]);

  return (
    <View style={{ gap: Space.xl }}>
      <Card>
        <View style={{ flexDirection: "row", justifyContent: "space-between", gap: Space.sm }}>
          <T variant="heading" style={{ flexShrink: 1 }}>
            {me.email}
          </T>
          {me.roles.length > 0 && <Badge>{me.roles.join(", ")}</Badge>}
        </View>
        {p ? (
          <View style={{ gap: 2, marginTop: Space.sm }}>
            <T variant="muted">Class: {p.grade ? GRADE_LABEL[p.grade] : "Not set"}</T>
            <T variant="muted">
              Subjects: {p.subjects?.length ? p.subjects.map((s) => s.replace("_", " ")).join(", ") : "Not set"}
            </T>
            <T variant="muted">
              Entry tests: {p.target_exams?.length ? p.target_exams.map((e) => e.toUpperCase()).join(", ") : "None"}
            </T>
            <T variant="muted">Daily study time: {p.daily_minutes ? `${p.daily_minutes} minutes` : "Not set"}</T>
          </View>
        ) : (
          <T variant="muted" style={{ marginTop: Space.sm }}>
            Tell us your class and subjects so we can show the right books.
          </T>
        )}
        <View style={{ marginTop: Space.md }}>
          <Button
            variant="secondary"
            label={p ? "Edit learning preferences" : "Set up learning preferences"}
            onPress={() => router.push("/onboarding")}
          />
        </View>
      </Card>

      <View style={{ gap: Space.sm }}>
        <T variant="heading" accessibilityRole="header">
          Signed-in devices
        </T>
        {sessions.state.status === "loading" && <Loading label="Loading devices" />}
        {sessions.state.status === "error" && <ErrorState error={sessions.state.error} onRetry={sessions.retry} />}
        {sessions.state.status === "success" && (
          <>
            {sessions.state.data.map((s: AppSession) => (
              <Card key={s.id}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flexWrap: "wrap" }}>
                  <T style={{ fontWeight: "600" }}>{s.device_label ?? (s.kind === "web" ? "Web browser" : "Mobile app")}</T>
                  {s.current && <Badge>This device</Badge>}
                </View>
                <T variant="small">
                  Last active {when(s.last_seen_at)} · signed in {when(s.created_at)}
                </T>
                {!s.current && (
                  <View style={{ marginTop: Space.sm, alignSelf: "flex-start" }}>
                    <Button
                      variant="secondary"
                      label="Sign out"
                      busy={busy === s.id}
                      onPress={() => act(s.id, () => api.revokeSession(token, s.id))}
                    />
                  </View>
                )}
              </Card>
            ))}
            {sessions.state.data.length > 1 && (
              <Button
                variant="link"
                label="Sign out everywhere else"
                busy={busy === "others"}
                onPress={() => act("others", () => api.revokeOthers(token))}
              />
            )}
          </>
        )}
      </View>

      <View style={{ borderTopWidth: 1, borderColor: c.border, paddingTop: Space.lg }}>
        <Button variant="secondary" label="Sign out of this device" busy={busy === "signout"} onPress={() => act("signout", signOut)} />
      </View>
    </View>
  );
}
