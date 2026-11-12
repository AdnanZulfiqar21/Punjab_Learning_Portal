import type { ReactNode } from "react";
import { BrandMark } from "@/components/brand-mark";
import { PageIcon } from "@/components/learner-pages";

// AUTH-PREMIUM-01 (owner 2026-11-12): on a computer the form sits beside a panel that says what Sirf Concepts is
// (draft A); on a phone it is one focused card with the logo on top (draft B).

const SUBJECTS = [
  { name: "Biology", dot: "#7fc9ad" },
  { name: "Chemistry", dot: "#e3a376" },
  { name: "Physics", dot: "#a9adf0" },
  { name: "Computer Science", dot: "#6cc4dc" },
  { name: "Mathematics", dot: "#e3a0cf" },
] as const;

const BARS = ["#0f7a62", "#9a4b00", "#3f46b5", "#0b5d73", "#8a2a6a"] as const;

const POINTS = [
  ["English + Roman Urdu", "for every topic"],
  ["Short lecture videos", "for each topic"],
  ["Chapter practice and mock tests", "in the Board pattern"],
] as const;

export function AuthShell({ title, lead, children }: { title: ReactNode; lead?: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-md pt-2 sm:pt-8 lg:max-w-6xl">
      <div className="lg:grid lg:grid-cols-[1.05fr_1fr] lg:overflow-hidden lg:rounded-[28px] lg:border lg:border-border lg:shadow-[0_30px_80px_-40px_rgb(11_93_115/0.45)]">
        <aside className="auth-story relative hidden flex-col justify-between gap-10 overflow-hidden p-10 text-[#eaf6f9] lg:flex">
          <div className="relative z-10 flex items-center gap-3 font-display text-xl font-bold text-white">
            <BrandMark id="auth-story" className="size-10 rounded-[11px]" />
            <span>
              Sirf <span className="text-[#ffd463]">Concepts</span>
            </span>
          </div>
          <div className="relative z-10 space-y-3">
            <p className="max-w-md font-display text-[2.5rem] leading-[1.1] font-bold tracking-tight text-white">
              Every Punjab Class 11 &amp; 12 book, <span className="text-[#ffd463]">explained simply.</span>
            </p>
            <p className="max-w-sm text-[#cfe8ee]">
              Read each chapter as printed in English, understand it in Roman Urdu, then practise.
            </p>
          </div>
          <ul className="relative z-10 space-y-3">
            {POINTS.map(([strong, rest]) => (
              <li key={strong} className="flex items-start gap-3">
                <span className="grid size-6 shrink-0 place-items-center rounded-md bg-white/15 text-[#ffd463]">
                  <PageIcon name="check" size={16} strokeWidth={2.6} />
                </span>
                <span>
                  <b className="font-semibold text-white">{strong}</b> {rest}
                </span>
              </li>
            ))}
          </ul>
          <ul className="relative z-10 flex flex-wrap gap-2" aria-label="Subjects">
            {SUBJECTS.map((s) => (
              <li
                key={s.name}
                className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-sm font-medium"
              >
                <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: s.dot }} />
                {s.name}
              </li>
            ))}
          </ul>
        </aside>
        <div className="relative lg:grid lg:place-items-center lg:bg-surface-muted/40 lg:p-10">
          <div className="glass w-full space-y-6 rounded-card px-5 py-7 sm:px-8 sm:py-9 lg:max-w-[440px]">
            <header className="space-y-2 text-center lg:text-left">
              <div className="flex flex-col items-center gap-3 pb-1 lg:hidden">
                <BrandMark id="auth-card" className="size-16 rounded-[18px] shadow-[0_12px_30px_-10px_rgb(11_93_115/0.6)]" />
                <span aria-hidden="true" className="flex gap-1.5">
                  {BARS.map((c) => (
                    <span key={c} className="h-1 w-7 rounded-full" style={{ background: c }} />
                  ))}
                </span>
              </div>
              <h1 className="font-display text-[1.75rem] leading-tight font-bold tracking-tight">{title}</h1>
              {lead && <p className="text-muted">{lead}</p>}
            </header>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
