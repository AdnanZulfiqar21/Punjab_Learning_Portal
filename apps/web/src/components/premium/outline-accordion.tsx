// PREMIUM-LOOK-01: the chapter outline in the side sheet, in the shadcn/ui "Accordion" look, with no JavaScript.
// Owner rules kept: every subtopic is listed under its topic, open, as the book's contents show it (2026-10-28); only
// the Mathematics "Book Examples" and "Exercise N.M" groups fold, and open smoothly when tapped (OUTLINE-FOLD-01).
// Numbers stay in the text colour.
import { BookOpen, ChevronDown, FileText, ListChecks } from "lucide-react";
import Link from "next/link";
import type { TopicNode } from "@portal/contracts";
import { cn } from "@/lib/cn";

function label(t: TopicNode) {
  return t.number ? `${t.number} ${t.title}` : t.title;
}

/** OUTLINE-FOLD-01: a group heading of the Mathematics outline over its pages. */
function isGroup(t: TopicNode) {
  return t.children.length > 0 && !t.number && /^(book examples|exercise \d)/i.test(t.title);
}

function iconFor(t: TopicNode) {
  if (/^(Exercise|Question)\b/.test(t.title)) return <ListChecks size={16} aria-hidden />;
  if (t.title === "Book Examples") return <BookOpen size={16} aria-hidden />;
  return <FileText size={16} aria-hidden />;
}

function BookNo({ t }: { t: TopicNode }) {
  return t.book_number ? <span className="ml-2 rounded-full border border-border px-2 py-0.5 text-xs font-normal text-muted">Book# {t.book_number}</span> : null;
}

function Leaf({ t, base, strong = false }: { t: TopicNode; base: string; strong?: boolean }) {
  return (
    <Link
      href={`${base}/${t.id}`}
      className={cn(
        "group flex min-h-11 items-start gap-2.5 rounded-xl px-3 py-2.5 text-foreground transition hover:bg-accent-soft hover:text-accent",
        strong ? "font-display text-[17px] font-semibold" : "text-[15px]",
      )}
    >
      <span className="mt-0.5 shrink-0 text-muted group-hover:text-accent">{iconFor(t)}</span>
      <span className="flex-1">
        {label(t)}
        <BookNo t={t} />
      </span>
    </Link>
  );
}

function Nodes({ nodes, base, nested = false }: { nodes: TopicNode[]; base: string; nested?: boolean }) {
  return (
    <div className={cn("space-y-2", nested && "mt-1 space-y-1 border-l border-border pl-3")}>
      {nodes.map((t) => {
        if (t.children.length === 0) return <Leaf key={t.id} t={t} base={base} strong={!nested} />;
        if (isGroup(t)) {
          const count = t.children.length;
          return (
            <details key={t.id} className={cn("outline-fold group/fold", !nested && "glass overflow-hidden rounded-2xl")}>
              <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2.5 rounded-xl px-3 py-2.5 text-[15px] font-semibold text-accent hover:bg-accent-soft [&::-webkit-details-marker]:hidden">
                <span className="shrink-0">{iconFor(t)}</span>
                <span className="flex-1">{t.title}</span>
                <span className="text-xs font-normal text-muted tabular-nums">
                  {count} {/^exercise/i.test(t.title) ? (count === 1 ? "question" : "questions") : count === 1 ? "page" : "pages"}
                </span>
                <ChevronDown size={18} aria-hidden className="shrink-0 text-muted transition-transform duration-300 group-open/fold:rotate-180" />
              </summary>
              <Nodes nodes={t.children} base={base} nested />
            </details>
          );
        }
        return (
          <div key={t.id} className={cn(!nested && "glass overflow-hidden rounded-2xl p-1")}>
            <Leaf t={t} base={base} strong={!nested} />
            <div className={cn(!nested && "px-2 pb-2")}>
              <Nodes nodes={t.children} base={base} nested />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function OutlineAccordion({ topics, base }: { topics: TopicNode[]; base: string }) {
  return <Nodes nodes={topics} base={base} />;
}
