"use client";

import { useRef, useState } from "react";

// The Lecture view of a topic (LECTURE-READ-01) on the web: the approved lecture's video with chapter markers and
// transcript. The stream comes through the site's own route (session cookie, range requests forwarded).
type Marker = { scene_id: string; label: string; start_s: number };
type Scene = { scene_id: string; text: string };

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export type LecturePart = { id: string; title: string; duration_s: number; src: string | null; markers: Marker[]; transcript: Scene[] };

export function LectureView({ parts }: { parts: LecturePart[] }) {
  const [index, setIndex] = useState(0);
  const part = parts[index] ?? parts[0];
  return (
    <div className="space-y-3">
      {parts.length > 1 && (
        <div role="group" aria-label="Lecture part" className="inline-flex flex-wrap gap-1 rounded-lg border border-border bg-surface-muted p-0.5">
          {parts.map((p, i) => (
            <button
              key={p.id}
              type="button"
              aria-pressed={i === index}
              onClick={() => setIndex(i)}
              className={`rounded-md px-3 py-1.5 text-sm ${i === index ? "bg-surface font-semibold shadow-sm" : "text-muted hover:text-foreground"}`}
            >
              Part {i + 1}
            </button>
          ))}
        </div>
      )}
      <p className="text-sm text-muted">
        {part.title} · {mmss(part.duration_s)}
      </p>
      {part.src ? <Player key={part.id} src={part.src} title={part.title} markers={part.markers} transcript={part.transcript} /> : null}
    </div>
  );
}

function Player({ src, title, markers, transcript }: { src: string; title: string; markers: Marker[]; transcript: Scene[] }) {
  const video = useRef<HTMLVideoElement>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const jump = (s: number) => {
    const v = video.current;
    if (!v) return;
    v.currentTime = s;
    void v.play().catch(() => undefined);
  };
  return (
    <div className="space-y-3">
      <video ref={video} controls preload="metadata" playsInline aria-label={title} className="aspect-video w-full rounded-xl bg-black">
        <source src={src} type="video/mp4" />
      </video>
      {markers.length > 0 && (
        <nav aria-label="In this lecture" className="space-y-1">
          <p className="text-sm font-medium text-accent">In this lecture</p>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {markers.map((m) => (
              <li key={m.scene_id}>
                <button type="button" onClick={() => jump(m.start_s)} className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-surface-muted">
                  <span className="w-11 shrink-0 font-mono text-accent">{mmss(m.start_s)}</span>
                  <span>{m.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}
      {transcript.length > 0 && (
        <div className="space-y-2 text-sm">
          <button type="button" onClick={() => setShowTranscript((s) => !s)} className="font-medium text-accent underline underline-offset-2">
            {showTranscript ? "Hide the transcript" : "Read the transcript"}
          </button>
          {showTranscript && (
            <div className="space-y-2 text-muted">
              {transcript.map((t) => (
                <p key={t.scene_id}>{t.text}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
