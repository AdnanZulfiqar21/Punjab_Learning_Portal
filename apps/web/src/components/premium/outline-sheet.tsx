"use client";
// PREMIUM-LOOK-01: shadcn/ui "Sheet" — the chapter outline slides in over the lesson. Only the button is in the page;
// the sheet (Radix dialog) loads the first time it is opened. The outline itself is rendered on the server.
import { ListTree } from "lucide-react";
import dynamic from "next/dynamic";
import { useState, type ReactNode } from "react";

const SheetDialog = dynamic(() => import("./outline-sheet-dialog").then((m) => m.SheetDialog), { ssr: false });

export function OutlineSheet({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  return (
    <>
      <button
        type="button"
        aria-haspopup="dialog"
        onClick={() => {
          setLoaded(true);
          setOpen(true);
        }}
        className="glass inline-flex min-h-11 items-center gap-2 rounded-full px-4 text-sm font-semibold text-foreground transition hover:text-accent"
      >
        <ListTree size={17} aria-hidden />
        Chapter outline
      </button>
      {loaded && (
        <SheetDialog open={open} onOpenChange={setOpen} title={title}>
          {children}
        </SheetDialog>
      )}
    </>
  );
}
