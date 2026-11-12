"use client";
// SEARCH-SUGGEST-01 (owner, 2026-11-13: "jb yaha kuch search krty hain to yaha suggestions bhe any cheheya nechy"): a
// list under the search box while the learner types, of the chapters and topics whose titles match. It attaches to the
// static form's input (the form is part of the prerendered shell and is never re-rendered) as an ARIA combobox: arrow
// keys move through the list, Enter opens the highlighted one, Escape closes it. Enter with nothing highlighted still
// submits the form for the full search, lessons included.
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { SubjectIcon } from "@/components/icons";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { markTyped, suggestionHref, type Suggestion } from "@/lib/search-suggest";

const LIST_ID = "search-suggestions";
const optionId = (i: number) => `${LIST_ID}-${i}`;

export function SearchSuggestions({ inputId, formId }: { inputId: string; formId: string }) {
  const router = useRouter();
  const [items, setItems] = useState<Suggestion[]>([]);
  const [typed, setTyped] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const state = useRef({ items, open, active });
  useEffect(() => {
    state.current = { items, open, active };
  });

  useEffect(() => {
    const input = document.getElementById(inputId) as HTMLInputElement | null;
    const form = document.getElementById(formId) as HTMLFormElement | null;
    if (!input || !form) return;
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", LIST_ID);
    input.setAttribute("autocomplete", "off");
    let timer: ReturnType<typeof setTimeout> | undefined;
    let ctrl: AbortController | undefined;
    const close = () => {
      setOpen(false);
      setActive(-1);
    };
    const load = () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) {
        ctrl?.abort();
        setItems([]);
        close();
        return;
      }
      timer = setTimeout(() => {
        ctrl?.abort();
        ctrl = new AbortController();
        const params = new URLSearchParams({ q });
        const grade = (form.elements.namedItem("grade") as HTMLSelectElement | null)?.value;
        const subject = (form.elements.namedItem("subject") as HTMLSelectElement | null)?.value;
        if (grade) params.set("grade", grade);
        if (subject) params.set("subject", subject);
        fetch(`/search/suggest?${params.toString()}`, { signal: ctrl.signal })
          .then((r) => r.json() as Promise<{ items?: Suggestion[] }>)
          .then((d) => {
            setItems(d.items ?? []);
            setTyped(q);
            setActive(-1);
            setOpen(document.activeElement === input);
          })
          .catch(() => {});
      }, 180);
    };
    const onKey = (e: KeyboardEvent) => {
      const { items: list, open: shown, active: at } = state.current;
      if (e.key === "Escape") {
        if (shown) e.preventDefault();
        close();
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!list.length) return;
        e.preventDefault();
        setOpen(true);
        const step = e.key === "ArrowDown" ? 1 : -1;
        setActive(shown ? nextIndex(at, step, list.length) : step > 0 ? 0 : list.length - 1);
      } else if (e.key === "Enter" && shown && at >= 0 && list[at]) {
        e.preventDefault();
        close();
        router.push(suggestionHref(list[at]));
      }
    };
    const onFocus = () => {
      if (state.current.items.length && input.value.trim().length >= 2) setOpen(true);
    };
    const onBlur = () => setTimeout(close, 120);
    input.addEventListener("input", load);
    input.addEventListener("keydown", onKey);
    input.addEventListener("focus", onFocus);
    input.addEventListener("blur", onBlur);
    form.addEventListener("change", load);
    form.addEventListener("submit", close);
    return () => {
      clearTimeout(timer);
      ctrl?.abort();
      input.removeEventListener("input", load);
      input.removeEventListener("keydown", onKey);
      input.removeEventListener("focus", onFocus);
      input.removeEventListener("blur", onBlur);
      form.removeEventListener("change", load);
      form.removeEventListener("submit", close);
    };
  }, [inputId, formId, router]);

  const shown = open && typed.length >= 2;
  useEffect(() => {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.setAttribute("aria-expanded", shown ? "true" : "false");
    if (shown && active >= 0) input.setAttribute("aria-activedescendant", optionId(active));
    else input.removeAttribute("aria-activedescendant");
    if (active >= 0) document.getElementById(optionId(active))?.scrollIntoView({ block: "nearest" });
  }, [inputId, shown, active]);

  if (!shown) return <ul id={LIST_ID} role="listbox" aria-label="Suggestions" hidden />;
  return (
    <ul
      id={LIST_ID}
      role="listbox"
      aria-label="Suggestions"
      className="glass absolute inset-x-0 top-full z-30 mt-2 max-h-[min(26rem,60vh)] overflow-y-auto rounded-card p-2 shadow-glass"
    >
      {items.length === 0 ? (
        <li role="presentation" className="px-3 py-3 text-sm text-muted">
          No chapter or topic is named like “{typed}”. Press Search to look inside the lessons too.
        </li>
      ) : (
        items.map((s, i) => (
          <li
            key={`${s.kind}-${s.id}`}
            id={optionId(i)}
            role="option"
            aria-selected={i === active}
            data-subject={subjectKey(s.subject_code)}
            onMouseDown={(e) => e.preventDefault()}
            onMouseEnter={() => setActive(i)}
            onClick={() => {
              setOpen(false);
              router.push(suggestionHref(s));
            }}
            className={`flex min-h-11 cursor-pointer items-center gap-3 rounded-inner px-3 py-2 ${i === active ? "bg-accent-soft" : ""}`}
          >
            <SubjectIcon subject={s.subject_code} size={32} />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-foreground">
                {s.number && s.kind === "topic" && <span className="mr-1.5 font-mono text-xs text-muted">{s.number}</span>}
                {markTyped(s.title, typed).map((p, k) =>
                  p.match ? (
                    <mark key={k} className="rounded bg-accent-soft px-0.5 font-semibold text-foreground">
                      {p.text}
                    </mark>
                  ) : (
                    <span key={k}>{p.text}</span>
                  ),
                )}
              </span>
              <span className="block truncate text-xs text-muted">
                {GRADE_LABEL[s.grade]} · {s.subject_name} · {s.kind === "chapter" ? "Chapter" : `Topic in ${s.chapter_title}`}
              </span>
            </span>
          </li>
        ))
      )}
    </ul>
  );
}

/** The next highlighted row; moving past either end goes back to the box (-1), and from the box into the list. */
function nextIndex(at: number, step: number, count: number): number {
  if (at === -1) return step > 0 ? 0 : count - 1;
  const next = at + step;
  return next < 0 || next >= count ? -1 : next;
}
