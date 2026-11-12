// AUTH-PASSWORD-01 + AUTH-PREMIUM-01 (owner 2026-11-12): sign-in, sign-up and the forgotten-password steps in the app.
// The phone layout the owner chose (draft B): one glass card with the logo and the subject colours on top, Sign in |
// Create account tabs, sign-up in two short steps. Drawn with plain views and CSS gradients (no extra libraries).
import { Image } from "expo-image";
import { useState, type ReactNode } from "react";
import { ActivityIndicator, Pressable, Switch, Text, TextInput, View, type TextInputProps } from "react-native";

import { FormError } from "@/components/form";
import { gradient } from "@/components/premium";
import { Notice, T } from "@/components/ui";
import { Glass, HeadingFont, Space } from "@/constants/theme";
import { useScheme, useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isoDate, looksLikeEmail, passwordStrength, STRENGTH_LABEL } from "@/lib/auth-input";

const problemTitle = (e: unknown) => (e instanceof ApiError ? e.problem?.title : undefined);
const offline = (e: unknown) => e instanceof ApiError && e.kind === "offline";
const OFFLINE = "Can't reach the learning service. Check your connection and try again.";
const WRONG_CODE = "That code is wrong or has expired. Check the email or ask for a new code.";
const BARS = ["#0f7a62", "#9a4b00", "#3f46b5", "#0b5d73", "#8a2a6a"] as const;
const BRAND = "linear-gradient(135deg, #1497ae 0%, #0b5d73 55%, #08485a 100%)";

type Mode = "signin" | "register" | "verify" | "forgot";

/* ---------- pieces ---------- */

function Card({ title, lead, children }: { title: string; lead?: string; children: ReactNode }) {
  const scheme = useScheme();
  const g = Glass[scheme];
  return (
    <View
      style={{
        backgroundColor: g.bg,
        borderColor: g.border,
        borderWidth: 1,
        borderRadius: 24,
        padding: Space.xl,
        gap: Space.lg,
        boxShadow: g.shadow,
      }}>
      <View style={{ alignItems: "center", gap: Space.sm }}>
        <Image
          source={require("@/assets/images/icon.png")}
          accessibilityIgnoresInvertColors
          accessible={false}
          style={{ width: 64, height: 64, borderRadius: 18 }}
        />
        <View style={{ flexDirection: "row", gap: 6 }} accessible={false}>
          {BARS.map((b) => (
            <View key={b} style={{ width: 26, height: 4, borderRadius: 2, backgroundColor: b }} />
          ))}
        </View>
        <T variant="heading" accessibilityRole="header" style={{ fontFamily: HeadingFont.bold, fontSize: 26, lineHeight: 32, textAlign: "center" }}>
          {title}
        </T>
        {lead ? (
          <T variant="muted" style={{ textAlign: "center" }}>
            {lead}
          </T>
        ) : null}
      </View>
      {children}
    </View>
  );
}

function Tabs({ mode, onChange }: { mode: "signin" | "register"; onChange: (m: "signin" | "register") => void }) {
  const c = useTheme();
  return (
    <View
      accessibilityRole="tablist"
      style={{ flexDirection: "row", padding: 4, borderRadius: 14, backgroundColor: c.surfaceMuted, borderWidth: 1, borderColor: c.border }}>
      {(["signin", "register"] as const).map((m) => {
        const on = mode === m;
        return (
          <Pressable
            key={m}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            onPress={() => !on && onChange(m)}
            style={{
              flex: 1,
              minHeight: 44,
              borderRadius: 10,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: on ? c.surface : "transparent",
              boxShadow: on ? "0px 2px 8px rgba(0,0,0,0.1)" : undefined,
            }}>
            <Text style={{ fontWeight: "600", fontSize: 15, color: on ? c.text : c.muted }}>{m === "signin" ? "Sign in" : "Create account"}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function Steps({ labels, at }: { labels: readonly string[]; at: number }) {
  const c = useTheme();
  return (
    <View accessibilityLabel={`Step ${at + 1} of ${labels.length}`} style={{ flexDirection: "row", alignItems: "center", gap: Space.sm }}>
      {labels.map((label, i) => (
        <View key={label} style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flex: i === 0 ? 0 : 1 }}>
          {i > 0 ? <View style={{ flex: 1, height: 2, borderRadius: 1, backgroundColor: i <= at ? c.accent : c.border }} /> : null}
          <View
            style={{
              width: 24,
              height: 24,
              borderRadius: 12,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: i <= at ? c.accent : "transparent",
              borderWidth: 1.5,
              borderColor: i <= at ? c.accent : c.border,
            }}>
            <Text style={{ fontSize: 12, fontWeight: "700", color: i <= at ? c.onAccent : c.muted }}>{i + 1}</Text>
          </View>
          {i === at ? <Text style={{ fontSize: 13, fontWeight: "600", color: c.text }}>{label}</Text> : null}
        </View>
      ))}
    </View>
  );
}

function Input({
  label,
  error,
  hint,
  secret,
  ...input
}: TextInputProps & { label: string; error?: string; hint?: string; secret?: boolean }) {
  const c = useTheme();
  const [shown, setShown] = useState(false);
  return (
    <View style={{ gap: Space.xs }}>
      <T style={{ fontWeight: "600" }}>{label}</T>
      <View style={{ justifyContent: "center" }}>
        <TextInput
          accessibilityLabel={label}
          aria-invalid={!!error}
          placeholderTextColor={c.muted}
          secureTextEntry={secret && !shown}
          style={{
            borderWidth: 1,
            borderColor: error ? c.danger : c.border,
            backgroundColor: c.surface,
            color: c.text,
            borderRadius: 14,
            paddingHorizontal: Space.lg,
            paddingRight: secret ? 72 : Space.lg,
            fontSize: 16,
            minHeight: 52,
          }}
          {...input}
        />
        {secret ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={shown ? "Hide password" : "Show password"}
            onPress={() => setShown((v) => !v)}
            hitSlop={8}
            style={{ position: "absolute", right: 6, minHeight: 44, minWidth: 56, alignItems: "center", justifyContent: "center", borderRadius: 10 }}>
            <Text style={{ color: c.accent, fontWeight: "600" }}>{shown ? "Hide" : "Show"}</Text>
          </Pressable>
        ) : null}
      </View>
      {hint ? <T variant="small">{hint}</T> : null}
      {error ? (
        <T variant="small" style={{ color: c.danger }} accessibilityLiveRegion="polite">
          {error}
        </T>
      ) : null}
    </View>
  );
}

function Strength({ value }: { value: string }) {
  const c = useTheme();
  const s = passwordStrength(value);
  return (
    <View style={{ gap: 4, marginTop: -Space.sm }}>
      <View style={{ flexDirection: "row", gap: 4 }} accessible={false}>
        {[1, 2, 3, 4].map((i) => (
          <View key={i} style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: i <= s ? (s >= 3 ? "#0f7a62" : "#d48c12") : c.border }} />
        ))}
      </View>
      <T variant="small" accessibilityLiveRegion="polite">
        {s ? `${STRENGTH_LABEL[s]}. ` : ""}At least 10 characters. A longer phrase is stronger.
      </T>
    </View>
  );
}

function Primary({ label, onPress, busy }: { label: string; onPress: () => void; busy?: boolean }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      aria-busy={!!busy}
      disabled={busy}
      onPress={onPress}
      style={({ pressed }) => [
        gradient(BRAND),
        {
          minHeight: 52,
          borderRadius: 14,
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "row",
          gap: Space.sm,
          opacity: busy ? 0.7 : pressed ? 0.88 : 1,
          boxShadow: "0px 10px 24px -10px rgba(11,93,115,0.7)",
        },
      ]}>
      {busy ? <ActivityIndicator color="#ffffff" /> : null}
      <Text style={{ color: "#ffffff", fontWeight: "700", fontSize: 16 }}>{label}</Text>
    </Pressable>
  );
}

function LinkButton({ label, onPress, muted }: { label: string; onPress: () => void; muted?: boolean }) {
  const c = useTheme();
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={{ minHeight: 44, justifyContent: "center" }}>
      <Text style={{ color: muted ? c.muted : c.accent, fontSize: 15, fontWeight: "600", textAlign: "center" }}>{label}</Text>
    </Pressable>
  );
}

/* ---------- the flow ---------- */

const TITLES: Record<Mode, [string, string]> = {
  signin: ["Welcome back", "Sign in to continue where you left off."],
  register: ["Create your account", "Sign up free to keep your place in each book and practise."],
  verify: ["Confirm your email", "Enter the 6-digit code we emailed you. It works for 15 minutes."],
  forgot: ["Reset your password", "We'll email you a 6-digit code, then you choose a new password."],
};

export function AuthForms() {
  const c = useTheme();
  const { signIn, register, verifyEmail, resendCode, resetPassword } = useAuth();
  const [mode, setMode] = useState<Mode>("signin");
  const [step, setStep] = useState<1 | 2>(1); // sign-up steps
  const [reset, setReset] = useState<"email" | "code" | "password">("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [surname, setSurname] = useState("");
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
  const [marketing, setMarketing] = useState(false);
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function go(next: Mode) {
    setError(null);
    setNotice(null);
    setFieldErrors({});
    setStep(1);
    setReset("email");
    setCode("");
    setMode(next);
  }

  function toVerify(message: string) {
    setCode("");
    setNotice(message);
    setMode("verify");
  }

  async function run(fn: () => Promise<void>) {
    setError(null);
    setNotice(null);
    setFieldErrors({});
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  }

  const submitSignIn = () =>
    run(async () => {
      if (!email.trim() || !password) return setError("Enter your email and password.");
      try {
        await signIn(email.trim(), password);
      } catch (e) {
        if (problemTitle(e) === "EMAIL_NOT_VERIFIED") {
          await resendCode(email.trim()).catch(() => undefined); // a recent code may still stand
          return toVerify("Confirm your email first. We sent you a 6-digit code.");
        }
        setError(
          offline(e) ? OFFLINE : e instanceof ApiError && e.kind === "unauthorized" ? "Email or password is incorrect." : "Sign-in is unavailable right now.",
        );
      }
    });

  function stepOneErrors(): Record<string, string> {
    const errs: Record<string, string> = {};
    if (!firstName.trim()) errs.first_name = "Enter your first name.";
    if (!surname.trim()) errs.surname = "Enter your surname.";
    if (!looksLikeEmail(email)) errs.email = "Enter a valid email address.";
    if (password.length < 10) errs.password = "Use at least 10 characters."; // pragma: allowlist secret
    return errs;
  }

  const toStepTwo = () => {
    const errs = stepOneErrors();
    setFieldErrors(errs);
    setError(null);
    if (!Object.keys(errs).length) setStep(2);
  };

  const submitRegister = () =>
    run(async () => {
      const first = stepOneErrors();
      if (Object.keys(first).length) {
        setStep(1);
        return setFieldErrors(first);
      }
      const errs: Record<string, string> = {};
      if (!phone.trim()) errs.phone = "Enter your mobile number.";
      const dateOfBirth = isoDate(dob);
      if (!dateOfBirth) errs.date_of_birth = "Enter your date of birth as DD/MM/YYYY.";
      if (Object.keys(errs).length) return setFieldErrors(errs);
      try {
        await register({
          email: email.trim(),
          password,
          first_name: firstName.trim(),
          surname: surname.trim(),
          phone: phone.trim(),
          date_of_birth: dateOfBirth!,
          marketing_emails: marketing,
        });
        toVerify("We emailed you a 6-digit code. It works for 15 minutes.");
      } catch (e) {
        if (e instanceof ApiError && e.kind === "invalid") {
          const fields = (e.problem?.errors ?? []).map((x) => String(x.loc.at(-1)));
          const known: Record<string, string> = {
            email: "Enter a valid email address.",
            first_name: "Enter your first name in letters.",
            surname: "Enter your surname in letters.",
            phone: "Enter a mobile number like 0300 1234567 (or +country code for other countries).",
            date_of_birth: "Enter your real date of birth.",
            password: "Use at least 10 characters.", // pragma: allowlist secret
          };
          const hit = fields.filter((f) => f in known);
          const shown = hit.length ? hit : ["email"];
          if (shown.some((f) => ["first_name", "surname", "email", "password"].includes(f))) setStep(1);
          return setFieldErrors(Object.fromEntries(shown.map((f) => [f, known[f]])));
        }
        setError(
          offline(e)
            ? OFFLINE
            : problemTitle(e) === "SERVICE_UNAVAILABLE"
              ? "We couldn't send the email just now. Please try again in a minute."
              : "Registration is unavailable right now.",
        );
      }
    });

  const submitCode = () =>
    run(async () => {
      const digits = code.replace(/\s/g, "");
      if (!/^\d{6}$/.test(digits)) return setFieldErrors({ code: "Enter the 6 digits from the email." });
      try {
        await verifyEmail(email.trim(), digits);
      } catch (e) {
        if (problemTitle(e) === "INVALID_CODE") return setFieldErrors({ code: WRONG_CODE });
        setError(offline(e) ? OFFLINE : "We couldn't check the code right now. Please try again.");
      }
    });

  const newCode = () =>
    run(async () => {
      try {
        await resendCode(email.trim());
        setNotice("A new code is on its way. Check your inbox (and the spam folder).");
      } catch (e) {
        const wait = (e instanceof ApiError ? (e.problem as { retry_after?: number } | null)?.retry_after : undefined) ?? 60;
        setError(
          offline(e) ? OFFLINE : problemTitle(e) === "RATE_LIMITED" ? `Please wait ${wait} seconds before asking for another code.` : "We couldn't send a new code right now.",
        );
      }
    });

  // Forgotten password: email → code (checked on its own) → new password.
  const askReset = (repeat?: boolean) =>
    run(async () => {
      if (!looksLikeEmail(email)) return setFieldErrors({ email: "Enter the email you signed up with." });
      try {
        await api.resetRequest(email.trim());
        setCode("");
        setReset("code");
        if (repeat) setNotice("If you asked less than a minute ago, the code already sent still works.");
      } catch (e) {
        setError(
          offline(e)
            ? OFFLINE
            : problemTitle(e) === "SERVICE_UNAVAILABLE"
              ? "We couldn't send the email just now. Please try again in a minute."
              : "We couldn't send the code right now. Please try again.",
        );
      }
    });

  const checkReset = () =>
    run(async () => {
      const digits = code.replace(/\s/g, "");
      if (!/^\d{6}$/.test(digits)) return setFieldErrors({ code: "Enter the 6 digits from the email." });
      try {
        await api.resetCheck(email.trim(), digits);
        setNewPassword("");
        setAgain("");
        setReset("password");
      } catch (e) {
        if (problemTitle(e) === "INVALID_CODE" || (e instanceof ApiError && e.kind === "invalid")) return setFieldErrors({ code: WRONG_CODE });
        setError(offline(e) ? OFFLINE : "We couldn't check the code right now. Please try again.");
      }
    });

  const finishReset = () =>
    run(async () => {
      if (newPassword.length < 10) return setFieldErrors({ new_password: "Use at least 10 characters." }); // pragma: allowlist secret
      if (newPassword !== again) return setFieldErrors({ confirm: "The two passwords don't match." });
      try {
        await resetPassword(email.trim(), code.replace(/\s/g, ""), newPassword);
      } catch (e) {
        if (problemTitle(e) === "INVALID_CODE") {
          setReset("code");
          return setFieldErrors({ code: WRONG_CODE });
        }
        setError(offline(e) ? OFFLINE : "We couldn't change the password right now. Please try again.");
      }
    });

  const [title, lead] = TITLES[mode];

  if (mode === "verify") {
    return (
      <Card title={title} lead={lead}>
        <T variant="muted">We sent it to {email.trim()}. Check the spam folder too.</T>
        {notice && <Notice title={notice} />}
        <CodeInput value={code} onChange={setCode} error={fieldErrors.code} onSubmit={submitCode} />
        <FormError message={error} />
        <Primary label="Confirm email" onPress={submitCode} busy={busy} />
        <LinkButton label="Send a new code" onPress={newCode} />
        <LinkButton label="Wrong email? Start again" onPress={() => go("register")} muted />
      </Card>
    );
  }

  if (mode === "forgot") {
    const at = reset === "email" ? 0 : reset === "code" ? 1 : 2;
    return (
      <Card title={title} lead={lead}>
        <Steps labels={["Email", "Code", "New password"]} at={at} />
        {notice && <Notice title={notice} />}
        {reset === "email" && (
          <>
            <Input
              label="Email"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              textContentType="username"
              placeholder="you@example.com"
              error={fieldErrors.email}
              onSubmitEditing={() => askReset()}
            />
            <FormError message={error} />
            <Primary label="Send code" onPress={() => askReset()} busy={busy} />
          </>
        )}
        {reset === "code" && (
          <>
            <T variant="muted">If an account uses {email.trim()}, we sent a 6-digit code to it. It works for 15 minutes.</T>
            <CodeInput value={code} onChange={setCode} error={fieldErrors.code} onSubmit={checkReset} />
            <FormError message={error} />
            <Primary label="Check code" onPress={checkReset} busy={busy} />
            <LinkButton label="Send a new code" onPress={() => askReset(true)} />
            <LinkButton label="Use a different email" onPress={() => setReset("email")} muted />
          </>
        )}
        {reset === "password" && (
          <>
            <T variant="muted">Code accepted. Choose a new password for {email.trim()}.</T>
            <Input
              label="New password"
              value={newPassword}
              onChangeText={setNewPassword}
              secret
              autoComplete="new-password"
              textContentType="newPassword"
              error={fieldErrors.new_password}
            />
            <Strength value={newPassword} />
            <Input
              label="Type it again"
              value={again}
              onChangeText={setAgain}
              secret
              autoComplete="new-password"
              textContentType="newPassword"
              error={fieldErrors.confirm}
              onSubmitEditing={finishReset}
            />
            <FormError message={error} />
            <Primary label="Save password and sign in" onPress={finishReset} busy={busy} />
            <T variant="small" style={{ textAlign: "center" }}>
              This also signs you out on every other device.
            </T>
          </>
        )}
        <LinkButton label="Remembered it? Sign in" onPress={() => go("signin")} />
      </Card>
    );
  }

  const registering = mode === "register";
  return (
    <Card title={title} lead={lead}>
      <Tabs mode={registering ? "register" : "signin"} onChange={go} />
      {registering && <Steps labels={["Your details", "Contact"]} at={step - 1} />}

      {(!registering || step === 1) && (
        <>
          {registering && (
            <>
              <Input
                label="First name"
                value={firstName}
                onChangeText={setFirstName}
                autoCapitalize="words"
                autoComplete="given-name"
                textContentType="givenName"
                maxLength={60}
                error={fieldErrors.first_name}
              />
              <Input
                label="Surname"
                value={surname}
                onChangeText={setSurname}
                autoCapitalize="words"
                autoComplete="family-name"
                textContentType="familyName"
                maxLength={60}
                error={fieldErrors.surname}
              />
            </>
          )}
          <Input
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            textContentType="username"
            placeholder="you@example.com"
            error={fieldErrors.email}
          />
          <Input
            label="Password"
            value={password}
            onChangeText={setPassword}
            secret
            autoComplete={registering ? "new-password" : "current-password"}
            textContentType={registering ? "newPassword" : "password"}
            error={fieldErrors.password}
            onSubmitEditing={registering ? toStepTwo : submitSignIn}
          />
          {registering ? <Strength value={password} /> : null}
          {!registering && (
            <View style={{ alignItems: "flex-end", marginTop: -Space.sm }}>
              <LinkButton label="Forgot password?" onPress={() => go("forgot")} />
            </View>
          )}
        </>
      )}

      {registering && step === 2 && (
        <>
          <Input
            label="Mobile number"
            value={phone}
            onChangeText={setPhone}
            placeholder="0300 1234567"
            keyboardType="phone-pad"
            autoComplete="tel"
            textContentType="telephoneNumber"
            hint="For your account only. We don't ask you to verify it."
            error={fieldErrors.phone}
          />
          <Input
            label="Date of birth (DD/MM/YYYY)"
            value={dob}
            onChangeText={setDob}
            placeholder="14/05/2008"
            keyboardType="numbers-and-punctuation"
            autoComplete="birthdate-full"
            error={fieldErrors.date_of_birth}
          />
          <View style={{ flexDirection: "row", alignItems: "center", gap: Space.md }}>
            <T variant="muted" style={{ flex: 1 }}>
              Send me news about new features and offers. You can stop these at any time.
            </T>
            <Switch
              accessibilityLabel="Send me news about new features and offers"
              value={marketing}
              onValueChange={setMarketing}
              trackColor={{ true: c.accent, false: c.border }}
            />
          </View>
        </>
      )}

      <FormError message={error} />
      {!registering && <Primary label="Sign in" onPress={submitSignIn} busy={busy} />}
      {registering && step === 1 && <Primary label="Continue" onPress={toStepTwo} />}
      {registering && step === 2 && (
        <>
          <Primary label="Create account" onPress={submitRegister} busy={busy} />
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: Space.md }}>
            <LinkButton label="← Back" onPress={() => setStep(1)} />
            <T variant="small" style={{ flex: 1, textAlign: "right" }}>
              We&apos;ll email you a 6-digit code.
            </T>
          </View>
        </>
      )}
      <LinkButton
        label={registering ? "Already have an account? Sign in" : "New here? Create an account"}
        onPress={() => go(registering ? "signin" : "register")}
      />
    </Card>
  );
}

function CodeInput({ value, onChange, error, onSubmit }: { value: string; onChange: (v: string) => void; error?: string; onSubmit: () => void }) {
  const c = useTheme();
  return (
    <View style={{ gap: Space.xs }}>
      <T style={{ fontWeight: "600" }}>6-digit code</T>
      <TextInput
        accessibilityLabel="6-digit code"
        value={value}
        onChangeText={onChange}
        keyboardType="number-pad"
        autoComplete="one-time-code"
        textContentType="oneTimeCode"
        maxLength={6}
        onSubmitEditing={onSubmit}
        aria-invalid={!!error}
        style={{
          borderWidth: 1,
          borderColor: error ? c.danger : c.border,
          backgroundColor: c.surface,
          color: c.text,
          borderRadius: 14,
          minHeight: 60,
          fontSize: 28,
          fontFamily: HeadingFont.semibold,
          letterSpacing: 10,
          textAlign: "center",
        }}
      />
      {error ? (
        <T variant="small" style={{ color: c.danger }} accessibilityLiveRegion="polite">
          {error}
        </T>
      ) : null}
    </View>
  );
}

