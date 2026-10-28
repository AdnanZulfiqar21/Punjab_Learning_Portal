// CODE-RUNNER-01 (app): "Run karein" under a printed Python program in the Roman Urdu tab, as on the web. The program
// runs on the device in a hidden WebView (lib/py-runner-page.ts), created only when the student first presses Run. A
// student may change only the program's plain values (lib/code-vars.ts) and answer its input() questions.
import { useMemo, useRef, useState } from "react";
import { Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";

import { T } from "@/components/ui";
import { CodeColors, Fonts, Radius, Space } from "@/constants/theme";
import { useScheme, useTheme } from "@/hooks/use-theme";
import { editableVars, inputPrompts, isPlainValue, withValues } from "@/lib/code-vars";
import { RUNNER_PAGE } from "@/lib/py-runner-page";

type Result = { output: string; error: string | null; timedOut?: boolean };
type Phase = "idle" | "loading" | "running";
type Message = { type: "loading" | "started" | "done" | "failed" | "timeout"; output?: string; error?: string | null };

export function CodeRunner({ code }: { code: string }) {
  const c = useTheme();
  const k = CodeColors[useScheme()];
  const vars = useMemo(() => editableVars(code), [code]);
  const prompts = useMemo(() => inputPrompts(code), [code]);
  const [values, setValues] = useState<Record<number, string>>({});
  const [answers, setAnswers] = useState<string[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<Result | null>(null);
  const [mounted, setMounted] = useState(false); // the WebView exists once Run was pressed
  const ready = useRef(false);
  const pending = useRef<string | null>(null);
  const web = useRef<WebView>(null);

  // The WebView needs a native build; the Expo web preview has none, so the button is not offered there.
  if (Platform.OS === "web") return null;

  const changed = Object.entries(values).some(([line, v]) => vars.find((x) => x.line === Number(line))?.value !== v);
  const invalid = Object.values(values).some((v) => !isPlainValue(v));
  const busy = phase !== "idle";

  function send(script: string) {
    if (ready.current) web.current?.injectJavaScript(script);
    else pending.current = script; // delivered when the page has loaded
  }

  function run() {
    if (busy || invalid) return;
    const job = { code: withValues(code, vars, values), stdin: prompts.map((_, i) => answers[i] ?? "") };
    setResult(null);
    setPhase("loading");
    setMounted(true);
    send(`window.__run(${JSON.stringify(job)}); true;`);
  }

  function onMessage(e: WebViewMessageEvent) {
    let m: Message;
    try {
      m = JSON.parse(e.nativeEvent.data) as Message;
    } catch {
      return;
    }
    if (m.type === "loading") setPhase("loading");
    else if (m.type === "started") setPhase("running");
    else {
      setPhase("idle");
      if (m.type === "done") setResult({ output: m.output ?? "", error: m.error ?? null });
      else if (m.type === "timeout") setResult({ output: "", error: null, timedOut: true });
      else setResult({ output: "", error: m.error || "Python load nahi ho saka. Internet check kar ke dobara koshish karein." });
    }
  }

  const box = { borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, backgroundColor: c.surface, paddingHorizontal: Space.sm, paddingVertical: 6 };
  const mono = { fontFamily: Fonts?.mono, fontSize: 14, color: c.text };

  return (
    <View
      accessibilityLabel="Program chala kar dekhein"
      style={{ borderWidth: 1, borderColor: c.accent, borderRadius: Radius.md, backgroundColor: c.accentSoft, padding: Space.md, gap: Space.sm }}>
      <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: Space.sm }}>
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ disabled: busy || invalid, busy }}
          disabled={busy || invalid}
          onPress={run}
          style={{ minHeight: 44, justifyContent: "center", paddingHorizontal: Space.lg, borderRadius: Radius.sm, backgroundColor: c.accent, opacity: busy || invalid ? 0.6 : 1 }}>
          <Text style={{ color: c.onAccent, fontWeight: "700", fontSize: 15 }}>{busy ? "Chal raha hai…" : "▶ Run karein"}</Text>
        </Pressable>
        {changed ? (
          <Pressable accessibilityRole="button" disabled={busy} onPress={() => setValues({})} style={{ minHeight: 44, justifyContent: "center", paddingHorizontal: Space.sm }}>
            <Text style={{ color: c.accent, fontWeight: "600" }}>Kitab wali values wapas</Text>
          </Pressable>
        ) : null}
      </View>

      {vars.length ? (
        <View style={{ gap: Space.xs }}>
          <T style={{ fontWeight: "600" }}>Values badal kar dekhein</T>
          {vars.map((v) => {
            const value = values[v.line] ?? v.value;
            return (
              <View key={v.line} style={{ flexDirection: "row", alignItems: "center", gap: Space.xs }}>
                <Text style={[mono, { color: k.variable }]}>{v.name} =</Text>
                <TextInput
                  value={value}
                  onChangeText={(t) => setValues((s) => ({ ...s, [v.line]: t }))}
                  autoCapitalize="none"
                  autoCorrect={false}
                  accessibilityLabel={`${v.name} ki value`}
                  style={[box, mono, { flex: 1, borderColor: isPlainValue(value) ? c.border : c.danger }]}
                />
              </View>
            );
          })}
          {invalid ? (
            <T variant="small" style={{ color: c.danger }}>
              {'Sirf value likhein: number (jaise 7), text quotes mein (jaise "Ali"), True/False, ya list (jaise [1, 2]).'}
            </T>
          ) : null}
        </View>
      ) : null}

      {prompts.length ? (
        <View style={{ gap: Space.xs }}>
          <T style={{ fontWeight: "600" }}>Program aap se poochega (input)</T>
          {prompts.map((p, i) => (
            <View key={i} style={{ gap: 2 }}>
              <Text style={mono}>{p || `Input ${i + 1}`}</Text>
              <TextInput
                value={answers[i] ?? ""}
                onChangeText={(t) => setAnswers((s) => Object.assign([...s], { [i]: t }))}
                autoCapitalize="none"
                autoCorrect={false}
                style={[box, mono]}
              />
            </View>
          ))}
        </View>
      ) : null}

      {busy || result ? (
        <View style={{ gap: Space.xs }} accessibilityLiveRegion="polite">
          <T variant="eyebrow" style={{ color: c.muted }}>
            Output
          </T>
          {phase === "loading" ? (
            <T variant="muted">Python load ho raha hai… pehli dafa thora waqt lagta hai.</T>
          ) : phase === "running" ? (
            <T variant="muted">Program chal raha hai…</T>
          ) : result?.timedOut ? (
            <T style={{ color: c.danger }}>Program 5 second mein khatam nahi hua, is liye rok diya (shayad loop kabhi khatam nahi hota).</T>
          ) : (
            <>
              {result?.output ? (
                <ScrollView horizontal style={box}>
                  <Text selectable style={mono}>
                    {result.output.trimEnd()}
                  </Text>
                </ScrollView>
              ) : !result?.error ? (
                <T variant="muted">(Program ne kuch print nahi kiya.)</T>
              ) : null}
              {result?.error ? (
                <View style={{ gap: 2 }}>
                  <T style={{ color: c.danger, fontWeight: "600" }}>Program mein ghalti (error):</T>
                  <ScrollView horizontal style={[box, { backgroundColor: c.dangerSoft, borderColor: c.dangerSoft }]}>
                    <Text selectable style={[mono, { fontSize: 12, color: c.danger }]}>
                      {result.error}
                    </Text>
                  </ScrollView>
                </View>
              ) : null}
            </>
          )}
        </View>
      ) : null}

      {mounted ? (
        <View style={{ width: 0, height: 0, overflow: "hidden" }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <WebView
            ref={web}
            source={{ html: RUNNER_PAGE, baseUrl: "https://localhost/" }}
            originWhitelist={["*"]}
            javaScriptEnabled
            onMessage={onMessage}
            onLoadEnd={() => {
              ready.current = true;
              if (pending.current) {
                web.current?.injectJavaScript(pending.current);
                pending.current = null;
              }
            }}
            onError={() => {
              setPhase("idle");
              setResult({ output: "", error: "Python load nahi ho saka. Internet check kar ke dobara koshish karein." });
            }}
          />
        </View>
      ) : null}
    </View>
  );
}
