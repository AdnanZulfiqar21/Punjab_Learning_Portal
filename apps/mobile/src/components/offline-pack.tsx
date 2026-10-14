// P13.S3 (OFFLINE-PACKS-01): save a chapter for offline reading and self-check practice. What is saved is exactly what
// this account may read online now; it is checked byte for byte, kept per account, refreshed when online, and removed
// on sign-out. Background downloads depend on the phone's operating system, so saving happens while this screen is open.
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { View } from "react-native";

import { Button } from "@/components/form";
import { Card, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { ApiError } from "@/lib/api";
import { downloadPack, PackError, readPack, refreshPack, removePack, type StoredPack } from "@/lib/study-packs";
import { TIME_ZONE } from "@/lib/dates";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "long", timeZone: TIME_ZONE });

export function OfflinePack({ token, owner, chapterId }: { token: string; owner: string; chapterId: string }) {
  const [pack, setPack] = useState<StoredPack | null>(() => readPack(owner, chapterId));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    refreshPack(token, owner, chapterId)
      .then((r) => {
        if (live && r === "removed") {
          setPack(null);
          setMessage("Your saved copy was removed: your plan no longer covers this chapter. You can save the free parts again.");
        }
      })
      .catch(() => undefined); // offline: keep what is saved until it expires
    return () => {
      live = false;
    };
  }, [token, owner, chapterId]);

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      setPack(await downloadPack(token, owner, chapterId));
    } catch (e) {
      setMessage(e instanceof PackError || e instanceof ApiError ? e.message : "Saving didn't finish. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <View style={{ gap: Space.sm }}>
        <T variant="heading">Use offline</T>
        {pack ? (
          <>
            <T variant="small">
              Saved on this device: {pack.manifest.lessons as number} lessons and {pack.manifest.questions as number} practice questions. Kept until{" "}
              {day(pack.manifest.expires_at)}.
            </T>
            {/* CONTENT-COMPAT-01: questions with images aren't packed yet; say so rather than leave them silently out. */}
            {Number(pack.manifest.questions_online_only ?? 0) > 0 ? (
              <T variant="small">
                {Number(pack.manifest.questions_online_only)} more practice question{Number(pack.manifest.questions_online_only) === 1 ? "" : "s"} with
                images or diagrams can be practised online only.
              </T>
            ) : null}
            <View style={{ flexDirection: "row", gap: Space.sm, flexWrap: "wrap" }}>
              <Button label="Open saved copy" onPress={() => router.push({ pathname: "/offline/[id]", params: { id: chapterId } })} />
              <Button variant="secondary" label="Update" busy={busy} onPress={save} />
              <Button
                variant="secondary"
                label="Remove"
                onPress={() => {
                  removePack(owner, chapterId);
                  setPack(null);
                }}
              />
            </View>
          </>
        ) : (
          <>
            <T variant="small">Save this chapter&apos;s lessons you can read now, and its practice questions, to study without a connection.</T>
            <Button variant="secondary" label="Save for offline" busy={busy} onPress={save} />
          </>
        )}
        {message ? <Notice tone="warn" title="Offline copy">{message}</Notice> : null}
      </View>
    </Card>
  );
}
