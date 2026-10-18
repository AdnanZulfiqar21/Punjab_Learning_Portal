// P13.S3 (OFFLINE-PACKS-01): save a chapter for offline reading and self-check practice. What is saved is exactly what
// this account may read online now; it is checked byte for byte, kept per account, refreshed when online, and removed
// on sign-out. Background downloads depend on the phone's operating system, so saving happens while this screen is open.
// Shown as one quiet row under the chapter's topics: a secondary action, not a panel.
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { View } from "react-native";

import { LinkButton, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { ApiError } from "@/lib/api";
import { downloadPack, PackError, readPack, refreshPack, removePack, type StoredPack } from "@/lib/study-packs";
import { TIME_ZONE } from "@/lib/dates";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "long", timeZone: TIME_ZONE });

export function OfflinePack({ token, owner, chapterId }: { token: string; owner: string; chapterId: string }) {
  const c = useTheme();
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
    <View style={{ gap: Space.xs, borderTopWidth: 1, borderTopColor: c.border, paddingTop: Space.sm }}>
      {pack ? (
        <>
          <T variant="small">
            Saved on this device: {pack.manifest.lessons as number} lessons, {pack.manifest.questions as number} practice questions · kept until{" "}
            {day(pack.manifest.expires_at)}.
            {/* CONTENT-COMPAT-01: questions with images aren't packed yet; say so rather than leave them silently out. */}
            {Number(pack.manifest.questions_online_only ?? 0) > 0
              ? ` ${Number(pack.manifest.questions_online_only)} more with diagrams can be practised online only.`
              : ""}
          </T>
          <View style={{ flexDirection: "row", gap: Space.md, flexWrap: "wrap" }}>
            <LinkButton label="Open saved copy" onPress={() => router.push({ pathname: "/offline/[id]", params: { id: chapterId } })} />
            <LinkButton label="Update" busy={busy} onPress={save} />
            <LinkButton
              label="Remove"
              onPress={() => {
                removePack(owner, chapterId);
                setPack(null);
              }}
            />
          </View>
        </>
      ) : (
        <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flexWrap: "wrap" }}>
          <T variant="small" style={{ flex: 1, minWidth: 160 }}>
            Read this chapter without a connection.
          </T>
          <LinkButton label="Save for offline" busy={busy} onPress={save} />
        </View>
      )}
      {message ? <Notice tone="warn" title="Offline copy">{message}</Notice> : null}
    </View>
  );
}
