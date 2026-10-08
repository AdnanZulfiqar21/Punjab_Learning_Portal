// Native written-script runner (W03/W04): write on paper, photograph each page, map pages to answer slots, submit once
// for a receipt. States stay honest: a photo chosen on this device, uploading, uploaded but NOT submitted, and
// submitted (sealed with a receipt). Nothing is marked until it is submitted; marks come from teachers.
import * as ImagePicker from "expo-image-picker";
import { Stack, useLocalSearchParams } from "expo-router";
import { useRef, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import type { WrittenAttempt } from "@portal/contracts";

import { Button, FormError } from "@/components/form";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { WrittenResultView } from "@/components/written-result";
import { Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Slot = { pages: string[]; unanswered: boolean };
type Upload = { key: string; name: string; status: "uploading" | "failed"; error?: string };
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
const newKey = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
const ACCEPTED = new Set(["image/jpeg", "image/png", "application/pdf"]);

export default function WrittenScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  if (state.status !== "signed_in") return <Notice title="Sign in to continue">Open the Account tab to sign in.</Notice>;
  return <Loader id={id} token={state.token} />;
}

function Loader({ id, token }: { id: string; token: string }) {
  const req = useRequest((signal) => api.writtenAttempt(token, id, signal), [token, id]);
  if (req.state.status === "loading") return <Loading label="Loading your written test" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const a = req.state.data;
  return <Runner key={`${a.id}:${a.status}`} initial={a} token={token} reload={req.retry} />;
}

function Runner({ initial, token, reload }: { initial: WrittenAttempt; token: string; reload: () => void }) {
  const c = useTheme();
  const [a, setA] = useState(initial);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [sealing, setSealing] = useState(false);
  const sealKey = useRef(newKey()); // one key for this submission; a retry returns the same receipt
  const slots = (a.manifest as { slots?: Record<string, Slot> }).slots ?? {};
  const open = a.status === "active";

  async function pick(source: "camera" | "library") {
    setError(null);
    const options: ImagePicker.ImagePickerOptions = {
      mediaTypes: ["images"],
      quality: 0.9,
      preferredAssetRepresentationMode: ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Compatible,
    };
    if (source === "camera") {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) {
        setError("Camera access is off. Allow it in your device settings, or choose photos instead.");
        return;
      }
    }
    const res =
      source === "camera"
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync({ ...options, allowsMultipleSelection: true, selectionLimit: 10 });
    if (res.canceled) return;
    for (const asset of res.assets) await send(asset);
  }

  async function send(asset: ImagePicker.ImagePickerAsset) {
    const key = newKey();
    const name = asset.fileName ?? "photo";
    if (asset.mimeType && !ACCEPTED.has(asset.mimeType)) {
      setUploads((u) => [...u, { key, name, status: "failed", error: "Only JPEG, PNG or PDF files are accepted." }]);
      return;
    }
    setUploads((u) => [...u, { key, name, status: "uploading" }]);
    try {
      const blob = await (await fetch(asset.uri)).blob();
      const out = await api.uploadWritten(token, a.id, blob);
      setWarnings(out.warnings);
      setUploads((u) => u.filter((x) => x.key !== key));
      setA(await api.writtenAttempt(token, a.id));
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "That didn't upload.";
      setUploads((u) => u.map((x) => (x.key === key ? { ...x, status: "failed", error: msg } : x)));
    }
  }

  async function save(next: Record<string, Slot>) {
    setSaving(true);
    setError(null);
    try {
      setA(await api.saveMapping(token, a.id, a.manifest_revision, next));
    } catch (e) {
      if (e instanceof ApiError && e.kind === "conflict") {
        setError("Your mapping changed on another device. The latest version has been loaded.");
        setA(await api.writtenAttempt(token, a.id));
      } else setError(e instanceof ApiError ? e.message : "Couldn't save the mapping.");
    } finally {
      setSaving(false);
    }
  }

  function toggle(slot: string, page: string) {
    const cur = slots[slot] ?? { pages: [], unanswered: false };
    const pages = cur.pages.includes(page) ? cur.pages.filter((p) => p !== page) : [...cur.pages, page];
    void save({ ...slots, [slot]: { pages, unanswered: pages.length ? false : cur.unanswered } });
  }

  function unanswered(slot: string) {
    const cur = slots[slot] ?? { pages: [], unanswered: false };
    void save({ ...slots, [slot]: { pages: cur.unanswered ? cur.pages : [], unanswered: !cur.unanswered } });
  }

  async function seal() {
    setSealing(true);
    setError(null);
    try {
      await api.sealWritten(token, a.id, sealKey.current, a.manifest_revision);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't submit. Your pages are still uploaded; try again.");
      setSealing(false);
    }
  }

  const allSlots = a.items.flatMap((it) => it.slots);
  const mapped = allSlots.filter((s) => (slots[s.key]?.pages.length ?? 0) > 0 || slots[s.key]?.unanswered).length;
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: a.linked_from ? "New practice test" : "Written test" }} />
      {a.status === "sealed" && a.receipt && (
        <Notice title="Submitted for marking">
          Receipt {a.receipt.id.slice(0, 8)} · {a.receipt.answered_slots} answered, {a.receipt.unanswered_slots} marked not answered · received{" "}
          {when(a.receipt.admitted_at)}. A teacher will mark it against the approved rubric.
        </Notice>
      )}
      {a.status === "expired" && (
        <Notice tone="warn" title="Upload window closed">
          This test wasn&apos;t submitted before the upload deadline, so it won&apos;t be marked. Its allowance was returned.
        </Notice>
      )}
      {open && (
        <Notice title="Not submitted yet">
          {a.writing_deadline_at ? `Stop writing at ${when(a.writing_deadline_at)}. ` : ""}Upload and map your pages, then submit before{" "}
          {when(a.upload_cutoff_at)}. Uploaded pages are not marked until you submit.
        </Notice>
      )}
      {a.status === "sealed" && <WrittenResultView attemptId={a.id} token={token} />}

      <T variant="heading" accessibilityRole="header">
        Questions
      </T>
      {a.items.map((it) => (
        <Card key={it.position}>
          <View style={{ gap: Space.sm }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T style={{ fontWeight: "600" }}>Question {it.position}</T>
              <Badge>{String(it.max_units / 100)} marks</Badge>
            </View>
            <LessonBlocks blocks={it.stem as { type: string }[]} />
            {(it.subparts as { id: string; label: string; blocks: { type: string }[] }[]).map((sp) => (
              <View key={sp.id} style={{ gap: Space.xs }}>
                <T style={{ fontWeight: "600" }}>{sp.label}</T>
                <LessonBlocks blocks={sp.blocks} />
              </View>
            ))}
          </View>
        </Card>
      ))}

      {open && (
        <>
          <T variant="heading" accessibilityRole="header">
            Your pages
          </T>
          <View style={{ flexDirection: "row", gap: Space.sm, flexWrap: "wrap" }}>
            <Button label="Take a photo" onPress={() => void pick("camera")} />
            <Button variant="secondary" label="Choose photos" onPress={() => void pick("library")} />
          </View>
          {uploads.map((u) => (
            <T key={u.key} variant="small" accessibilityRole={u.status === "failed" ? "alert" : undefined}>
              {u.name}: {u.status === "uploading" ? "uploading…" : `not uploaded — ${u.error}`}
            </T>
          ))}
          {warnings.map((w) => (
            <T key={w} variant="small">
              {w}
            </T>
          ))}
          {a.pages.length === 0 ? (
            <T variant="muted">No pages uploaded yet.</T>
          ) : (
            <T variant="small" accessibilityLabel="Uploaded pages">
              {a.pages.length} page(s) uploaded (not submitted): {a.pages.map((_, i) => `Page ${i + 1}`).join(", ")}
            </T>
          )}

          <T variant="heading" accessibilityRole="header">
            Which pages answer which part?
          </T>
          {allSlots.map((s) => {
            const cur = slots[s.key] ?? { pages: [], unanswered: false };
            return (
              <Card key={s.key} label={s.label}>
                <View style={{ gap: Space.xs }}>
                  <T style={{ fontWeight: "600" }}>{s.label}</T>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.xs }}>
                    {a.pages.map((p, i) => {
                      const on = cur.pages.includes(p.id);
                      return (
                        <Pressable
                          key={p.id}
                          accessibilityRole="checkbox"
                          accessibilityLabel={`${s.label}: page ${i + 1}`}
                          aria-checked={on}
                          disabled={saving}
                          onPress={() => toggle(s.key, p.id)}
                          style={{
                            paddingHorizontal: Space.md,
                            paddingVertical: Space.sm,
                            borderRadius: Radius.pill,
                            borderWidth: 1,
                            borderColor: on ? c.accent : c.border,
                            backgroundColor: on ? c.accentSoft : c.surface,
                          }}>
                          <T variant="small">Page {i + 1}</T>
                        </Pressable>
                      );
                    })}
                  </View>
                  <Pressable
                    accessibilityRole="checkbox"
                    accessibilityLabel={`${s.label}: I didn't answer this`}
                    aria-checked={cur.unanswered}
                    disabled={saving}
                    onPress={() => unanswered(s.key)}>
                    <T variant="small">{cur.unanswered ? "☑" : "☐"} I didn&apos;t answer this</T>
                  </Pressable>
                </View>
              </Card>
            );
          })}
          <T variant="small" accessibilityRole="text">
            {saving ? "Saving…" : `Saved · revision ${a.manifest_revision}`} · {mapped} of {allSlots.length} parts mapped
          </T>
          <FormError message={error} />
          <Button
            label="Submit for marking"
            onPress={() => void seal()}
            busy={sealing}
            disabled={saving || mapped < allSlots.length}
          />
          <T variant="small">Every part needs a page or &quot;I didn&apos;t answer this&quot;. You can submit once; after that nothing changes.</T>
        </>
      )}
      {!open && <FormError message={error} />}
    </ScrollView>
  );
}
