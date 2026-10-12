// P10.S4.T3 (EXAM-ROOM-01): while a mock runs, other tests, results, the notebook and study packs are closed. This says
// so and offers the way back to the mock, instead of a generic error.
import { router } from "expo-router";
import { View } from "react-native";

import { Button } from "@/components/form";
import { Notice } from "@/components/ui";
import { Space } from "@/constants/theme";
import { ApiError } from "@/lib/api";

/** The running mock's attempt id when this error is the exam-room refusal. */
export function mockRunning(e: unknown): string | null {
  const p = e instanceof ApiError ? (e.problem as { code_reason?: string; attempt_id?: string } | null | undefined) : null;
  return p?.code_reason === "MOCK_IN_PROGRESS" && p.attempt_id ? p.attempt_id : null;
}

export function MockRunningNotice({ attemptId }: { attemptId: string }) {
  return (
    <View style={{ padding: Space.lg, gap: Space.md }}>
      <Notice tone="warn" title="Your mock test is still running">
        Other tests, results, the mistake notebook and study packs open again when you submit it or its time is up.
      </Notice>
      <View style={{ alignSelf: "flex-start" }}>
        <Button label="Back to your mock" onPress={() => router.replace({ pathname: "/attempt/[id]", params: { id: attemptId } })} />
      </View>
    </View>
  );
}
