"use client";

// Sends the lesson.started analytics event once when a readable lesson is shown (P16.S2.T1). Failures are ignored:
// analytics never blocks reading.
import { useEffect } from "react";
import { recordLessonStart } from "@/app/actions/lessons";

export function LessonStartBeacon({ lessonId, language }: { lessonId: string; language: string }) {
  useEffect(() => {
    recordLessonStart(lessonId, language).catch(() => undefined);
  }, [lessonId, language]);
  return null;
}
