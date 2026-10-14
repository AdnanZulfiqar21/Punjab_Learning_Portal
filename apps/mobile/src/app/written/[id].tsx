// Native written-script runner (W03/W04): write on paper, photograph each page, map pages to answer slots, submit once
// for a receipt. States stay honest: on this phone but not sent yet (kept safely until it uploads; CAPTURE-01),
// uploaded but NOT submitted, and submitted (sealed with a receipt). Nothing is marked until it is submitted; marks
// come from teachers. Submitting is refused while a page is unsent or anything is still moving (OCT14-01); the rules
// are in lib/written-pages.ts and tested on the host.
import * as ImagePicker from "expo-image-picker";
import { Stack, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { Image } from "expo-image";
import { Linking, Pressable, ScrollView, View } from "react-native";
import type { WrittenAttempt, WrittenPage } from "@portal/contracts";

import { Button, FormError } from "@/components/form";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { WrittenResultView } from "@/components/written-result";
import { Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError, writtenPageImage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TIME_ZONE } from "@/lib/dates";
import { clearAttempt, keepPage, listPages, notePageError, pickPdf, removePage } from "@/lib/page-drafts";
import { WrittenPages } from "@/lib/written-pages";

type Slot = { pages: string[]; unanswered: boolean };
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });
const newKey = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
const mb = (n: number) => `${Math.max(1, Math.round(n / (1024 * 1024)))} MB`;

export default function WrittenScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  if (state.status !== "signed_in") return <Notice title="Sign in to continue">Open the Account tab to sign in.</Notice>;
  return <Loader id={id} token={state.token} owner={state.me.id} />;
}

function Loader({ id, token, owner }: { id: string; token: string; owner: string }) {
  const req = useRequest((signal) => api.writtenAttempt(token, id, signal), [token, id]);
  if (req.state.status === "loading") return <Loading label="Loading your written test" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const a = req.state.data;
  return <Runner key={`${a.id}:${a.status}`} initial={a} token={token} owner={owner} reload={req.retry} />;
}

function Runner({ initial, token, owner, reload }: { initial: WrittenAttempt; token: string; owner: string; reload: () => void }) {
  const c = useTheme();
  const [a, setA] = useState(initial);
  const open = a.status === "active";
  const [pages] = useState(
    () =>
      new WrittenPages(
        {
          keepPage: (source) => keepPage(owner, initial.id, source),
          removePage: (pageId) => removePage(owner, initial.id, pageId),
          notePageError: (draft, msg) => notePageError(owner, initial.id, draft, msg),
          upload: async (draft) => {
            const blob = await (await fetch(draft.uri)).blob();
            await api.uploadWritten(token, initial.id, blob); // SCAN-QUALITY-01: its warnings are shown with each page
            try {
              setA(await api.writtenAttempt(token, initial.id));
            } catch {
              /* the page is uploaded; the list catches up on the next change */
            }
          },
          seal: (key, revision) => api.sealWritten(token, initial.id, key, revision),
          message: (e, fallback) => (e instanceof ApiError ? e.message : fallback),
          newKey,
        },
        initial.status === "active" ? listPages(owner, initial.id) : [],
      ),
  );
  useSyncExternalStore(
    useCallback((listener) => pages.subscribe(listener), [pages]),
    () => pages.version,
  );
  // CAPTURE-01, OCT14-01: pages left on this phone for a test that has closed can't be submitted any more. They are
  // kept until the learner removes them (or signs out), never deleted behind their back.
  const [leftover, setLeftover] = useState(() => (initial.status === "active" ? [] : listPages(owner, initial.id)));
  const [cameraDenied, setCameraDenied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const slots = (a.manifest as { slots?: Record<string, Slot> }).slots ?? {};

  // Send what is still on the phone as soon as the test is open again.
  useEffect(() => {
    if (!open) return;
    void (async () => {
      for (const d of [...pages.pending]) await pages.resend(d.id);
    })();
  }, [open, pages]);

  async function pick(source: "camera" | "library" | "pdf") {
    if (!pages.canCapture()) return;
    setError(null);
    setCameraDenied(false);
    await pages.track(async () => {
      if (source === "pdf") {
        try {
          const doc = await pickPdf();
          if (doc) await pages.capture(doc);
        } catch (e) {
          setError(e instanceof Error ? e.message : "Couldn't open your files.");
        }
        return;
      }
      const options: ImagePicker.ImagePickerOptions = {
        mediaTypes: ["images"],
        quality: 0.9,
        preferredAssetRepresentationMode: ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Compatible,
      };
      if (source === "camera") {
        const perm = await ImagePicker.requestCameraPermissionsAsync();
        if (!perm.granted) {
          setCameraDenied(true); // shown with a way to the settings, and the other ways to add pages
          return;
        }
      }
      const res =
        source === "camera"
          ? await ImagePicker.launchCameraAsync(options)
          : await ImagePicker.launchImageLibraryAsync({ ...options, allowsMultipleSelection: true, selectionLimit: 10 });
      if (res.canceled) return;
      for (const asset of res.assets) {
        await pages.capture({ uri: asset.uri, name: asset.fileName ?? "photo", mimeType: asset.mimeType ?? "image/jpeg", size: asset.fileSize });
      }
    });
  }

  async function save(next: Record<string, Slot>) {
    setSaving(true);
    setError(null);
    await pages.track(async () => {
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
    });
  }

  function toggle(slot: string, page: string) {
    const cur = slots[slot] ?? { pages: [], unanswered: false };
    const next = cur.pages.includes(page) ? cur.pages.filter((p) => p !== page) : [...cur.pages, page];
    void save({ ...slots, [slot]: { pages: next, unanswered: next.length ? false : cur.unanswered } });
  }

  function unanswered(slot: string) {
    const cur = slots[slot] ?? { pages: [], unanswered: false };
    void save({ ...slots, [slot]: { pages: cur.unanswered ? cur.pages : [], unanswered: !cur.unanswered } });
  }

  async function seal() {
    setError(null);
    const out = await pages.seal(mapped, allSlots.length, a.manifest_revision); // checks the gate again, now
    if (out.ok) reload();
    else setError(out.reason);
  }

  const allSlots = a.items.flatMap((it) => it.slots);
  const mapped = allSlots.filter((s) => (slots[s.key]?.pages.length ?? 0) > 0 || slots[s.key]?.unanswered).length;
  const blocked = pages.blocker(mapped, allSlots.length);
  const pending = pages.pending;
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: a.linked_from ? "New practice test" : "Written test" }} />
      {a.status === "sealed" && a.receipt && (
        <Notice title="Submitted for marking">
          Receipt {a.receipt.id.slice(0, 8)} · {a.receipt.answered_slots} answered, {a.receipt.unanswered_slots} marked not answered · received{" "}
          {when(a.receipt.admitted_at)}. A teacher will mark it against the approved rubric.
        </Notice>
      )}
      {a.status === "expired" && a.end_reason === "plan_withdrawn" && (
        <Notice tone="warn" title="Ended: plan withdrawn">
          This test ended because your plan was withdrawn. Pages you uploaded are kept but weren&apos;t submitted. Tests you had
          already submitted are still marked.
        </Notice>
      )}
      {a.status === "expired" && a.end_reason !== "plan_withdrawn" && (
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
      {!open && leftover.length > 0 && (
        <View style={{ gap: Space.sm }}>
          <Notice tone="warn" title="Pages on this phone that were never sent">
            {leftover.length} page{leftover.length === 1 ? "" : "s"} you added to this test stayed on this phone and never reached us, so
            {leftover.length === 1 ? " it isn't" : " they aren't"} part of what was received. This test is closed, so they can&apos;t be added
            now. They stay on this phone until you remove them or sign out.
          </Notice>
          <Button
            variant="secondary"
            label="Remove them from this phone"
            onPress={() => {
              clearAttempt(owner, a.id);
              setLeftover([]);
            }}
          />
        </View>
      )}

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
            <Button label="Take a photo" disabled={pages.sealing} onPress={() => void pick("camera")} />
            <Button variant="secondary" label="Choose photos" disabled={pages.sealing} onPress={() => void pick("library")} />
            <Button variant="secondary" label="Choose a PDF" disabled={pages.sealing} onPress={() => void pick("pdf")} />
          </View>
          {pages.notice && (
            <T variant="small" accessibilityRole="alert" style={{ color: c.danger }}>
              {pages.notice}
            </T>
          )}
          {cameraDenied && (
            <View style={{ gap: Space.sm }}>
              <Notice tone="warn" title="Camera access is off">
                Allow the camera for this app in your phone&apos;s settings, or add pages with Choose photos or Choose a PDF instead.
              </Notice>
              <Button variant="secondary" label="Open settings" onPress={() => void Linking.openSettings()} />
            </View>
          )}
          {pages.lowStorage !== undefined && (
            <Notice tone="warn" title="Your phone is nearly full">
              {pages.lowStorage !== null ? `About ${mb(pages.lowStorage)} is free. ` : ""}New pages are being sent straight away but can&apos;t be kept on your
              phone, so if one doesn&apos;t upload you&apos;ll need to add it again. Free up some space to keep pages safely until they upload.
            </Notice>
          )}
          {pending.length > 0 && (
            <View accessibilityLabel="On this phone, not sent yet" style={{ gap: Space.xs }}>
              <T style={{ fontWeight: "600" }}>On this phone, not sent yet</T>
              {pending.map((d) => (
                <View key={d.id} style={{ gap: Space.xs, borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, padding: Space.sm }}>
                  <T variant="small" accessibilityRole={d.status === "failed" ? "alert" : undefined}>
                    {d.name}: {d.status === "sending" ? "sending…" : `not sent — ${d.error}`}
                    {d.kept ? " · kept on this phone" : " · not kept on this phone"}
                  </T>
                  {d.status === "failed" && (
                    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.xs }}>
                      <Button variant="secondary" label="Send again" onPress={() => void pages.resend(d.id)} />
                      <Button variant="secondary" label="Remove" onPress={() => pages.discard(d.id)} />
                    </View>
                  )}
                </View>
              ))}
            </View>
          )}
          {a.pages.length === 0 ? (
            <T variant="muted">No pages uploaded yet.</T>
          ) : (
            <View accessibilityLabel="Uploaded pages" style={{ gap: Space.sm }}>
              {a.pages.map((p, i) => (
                <PageCard
                  key={p.id}
                  attemptId={a.id}
                  page={p}
                  number={i + 1}
                  token={token}
                  editable={a.status === "active" && !pages.sealing}
                  track={(work) => pages.track(work)}
                  onChange={(n) => setA((cur) => ({ ...cur, pages: cur.pages.map((x) => (x.id === n.id ? n : x)) }))}
                />
              ))}
            </View>
          )}
          {a.pages.flatMap((p, i) => (p.quality ?? []).map((q) => (
            <T key={`${p.id}-${q.code}`} variant="small" style={{ color: c.warn }}>
              Page {i + 1}: {q.message}
            </T>
          )))}
          {a.pages.some((p) => (p.quality ?? []).length > 0) && (
            <T variant="small">
              These are automatic checks, not a judgement: a teacher decides whether a page can be read. To use a clearer photo, add it and choose it
              for that answer below. A page you don&apos;t choose isn&apos;t sent for marking.
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
          <Button label="Submit for marking" onPress={() => void seal()} busy={pages.sealing} disabled={blocked !== null} />
          <T variant="small">
            {blocked && !pages.sealing ? `${blocked} ` : ""}Every part needs a page or &quot;I didn&apos;t answer this&quot;, and every page on
            this phone must be sent or removed. You can submit once; after that nothing changes.
          </T>
        </>
      )}
      {!open && <FormError message={error} />}
    </ScrollView>
  );
}

// W03.S1.T3 (MOBILE-TRANSFORMS-01): turn a page, make it clearer or trim its edges before submitting, as on the web.
// The server re-renders from the untouched original every time, so nothing is lost and a teacher can always see the
// original. A trim is a share of the page as shown (at most 30% from any side), mapped onto the original by the server.
const SIDES = [
  ["top", "Top"],
  ["bottom", "Bottom"],
  ["left", "Left"],
  ["right", "Right"],
] as const;
type Trim = Record<(typeof SIDES)[number][0], number>;
function PageCard({
  attemptId,
  page,
  number,
  token,
  editable,
  track,
  onChange,
}: {
  attemptId: string;
  page: WrittenPage;
  number: number;
  token: string;
  editable: boolean;
  track: <R>(work: () => Promise<R>) => Promise<R>; // counted as work in flight, so submitting waits for it
  onChange: (p: WrittenPage) => void;
}) {
  const c = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trimming, setTrimming] = useState(false);
  const [trim, setTrim] = useState<Trim>({ top: 0, bottom: 0, left: 0, right: 0 });
  const t = (page.transform ?? { rotate: 0, crop: null, enhance: false }) as { rotate: number; crop: number[] | null; enhance: boolean };
  async function apply(next: { rotate: number; enhance: boolean; crop?: number[] | null; trim?: number[] }) {
    setBusy(true);
    setError(null);
    await track(async () => {
      try {
        const body = { rotate: next.rotate, crop: next.crop === undefined ? (t.crop ?? null) : next.crop, enhance: next.enhance };
        onChange(await api.transformPage(token, attemptId, page.id, next.trim ? { ...body, trim: next.trim } : body));
        if (next.trim) setTrim({ top: 0, bottom: 0, left: 0, right: 0 });
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Couldn't change this page.");
      } finally {
        setBusy(false);
      }
    });
  }
  return (
    <View style={{ gap: Space.xs, borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, padding: Space.sm }}>
      <Image
        source={writtenPageImage(attemptId, page, token)}
        accessibilityLabel={`Page ${number}`}
        accessible
        contentFit="contain"
        style={{ width: "100%", height: 200 }}
      />
      <T variant="small">
        Page {number} · {editable ? "uploaded, not yet submitted" : "submitted"}
        {t.rotate ? ` · turned ${t.rotate}°` : ""}
        {t.enhance ? " · clearer contrast" : ""}
        {t.crop ? " · trimmed" : ""}
      </T>
      {editable ? (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.xs }}>
          <Button variant="secondary" label="Turn left" busy={busy} onPress={() => void apply({ rotate: (t.rotate + 270) % 360, enhance: t.enhance })} />
          <Button variant="secondary" label="Turn right" busy={busy} onPress={() => void apply({ rotate: (t.rotate + 90) % 360, enhance: t.enhance })} />
          <Button
            variant="secondary"
            label={t.enhance ? "Original contrast" : "Clearer contrast"}
            busy={busy}
            onPress={() => void apply({ rotate: t.rotate, enhance: !t.enhance })}
          />
          <Button variant="secondary" label={trimming ? "Close trim" : "Trim edges"} onPress={() => setTrimming((v) => !v)} />
          {t.crop ? (
            <Button variant="secondary" label="Undo trim" busy={busy} onPress={() => void apply({ rotate: t.rotate, enhance: t.enhance, crop: null })} />
          ) : null}
        </View>
      ) : null}
      {editable && trimming ? (
        <View accessibilityLabel={`Trim page ${number}`} style={{ gap: Space.xs }}>
          {SIDES.map(([side, label]) => (
            <View key={side} style={{ flexDirection: "row", alignItems: "center", gap: Space.xs }}>
              <T variant="small" style={{ width: 64 }}>
                {label}
              </T>
              <Button
                variant="secondary"
                label="−"
                accessibilityLabel={`Trim less from the ${side}`}
                disabled={trim[side] === 0}
                onPress={() => setTrim((v) => ({ ...v, [side]: Math.max(0, v[side] - 5) }))}
              />
              <T variant="small" accessibilityLabel={`${trim[side]} percent from the ${side}`}>
                {trim[side]}%
              </T>
              <Button
                variant="secondary"
                label="+"
                accessibilityLabel={`Trim more from the ${side}`}
                disabled={trim[side] === 30}
                onPress={() => setTrim((v) => ({ ...v, [side]: Math.min(30, v[side] + 5) }))}
              />
            </View>
          ))}
          <Button
            variant="secondary"
            label="Trim"
            busy={busy}
            disabled={trim.top + trim.bottom + trim.left + trim.right === 0}
            onPress={() =>
              void apply({
                rotate: t.rotate,
                enhance: t.enhance,
                trim: [trim.left / 100, trim.top / 100, 1 - (trim.left + trim.right) / 100, 1 - (trim.top + trim.bottom) / 100],
              })
            }
          />
        </View>
      ) : null}
      <FormError message={error} />
    </View>
  );
}
