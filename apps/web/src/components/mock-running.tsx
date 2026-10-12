import Link from "next/link";
import { Notice } from "@/components/ui";

/** P10.S4.T3: shown instead of another test or result while the learner's mock is running. */
export function MockRunningNotice({ attemptId }: { attemptId: string }) {
  return (
    <Notice tone="warn" title="Your mock test is still running">
      Other tests, results, the mistake notebook and study packs open again when you submit it or its time is up.{" "}
      <Link href={`/practice/attempt/${attemptId}`} className="font-medium underline underline-offset-2">
        Back to your mock
      </Link>
    </Notice>
  );
}
