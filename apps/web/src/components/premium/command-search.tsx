"use client";
// PREMIUM-LOOK-01: shadcn/ui "Command" — press Ctrl K (or the button) and type to jump to any page of the chapter. Only
// the button is in the page; the dialog (cmdk + Radix) loads the first time it is opened, to keep the JS budget.
import { Search } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import type { SearchItem } from "./command-dialog";

export type { SearchItem };

const CommandDialog = dynamic(() => import("./command-dialog").then((m) => m.CommandDialog), { ssr: false });

export function CommandSearch({ items, base, placeholder }: { items: SearchItem[]; base: string; placeholder: string }) {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const show = (o: boolean) => {
    if (o) setLoaded(true);
    setOpen(o);
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setLoaded(true);
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <>
      <button
        type="button"
        onClick={() => show(true)}
        aria-haspopup="dialog"
        className="glass inline-flex min-h-11 w-full items-center gap-2 rounded-full px-4 text-sm text-muted transition hover:text-foreground sm:w-80"
      >
        <Search size={16} aria-hidden />
        <span className="flex-1 text-left">{placeholder}</span>
        <kbd className="hidden rounded-md border border-border px-1.5 py-0.5 text-[11px] font-semibold sm:inline">Ctrl K</kbd>
      </button>
      {loaded && <CommandDialog open={open} onOpenChange={show} items={items} base={base} placeholder={placeholder} />}
    </>
  );
}
