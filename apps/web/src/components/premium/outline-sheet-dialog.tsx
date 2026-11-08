"use client";
// PREMIUM-LOOK-01: the outline sheet itself (Radix dialog from the side), loaded on first open by OutlineSheet.
import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import type { ReactNode } from "react";

export function SheetDialog({ open, onOpenChange, title, children }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; children: ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" />
        <Dialog.Content className="sheet-content fixed inset-y-0 right-0 z-50 flex w-[min(28rem,100vw)] flex-col border-l border-border bg-background shadow-2xl">
          <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
            <Dialog.Title className="font-display text-lg font-semibold">{title}</Dialog.Title>
            <Dialog.Close aria-label="Close the outline" className="inline-flex size-11 items-center justify-center rounded-full hover:bg-surface-muted">
              <X size={18} aria-hidden />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Every page of this chapter, in the book&apos;s order.</Dialog.Description>
          <div className="flex-1 overflow-y-auto p-4" onClickCapture={(e) => (e.target as HTMLElement).closest("a") && onOpenChange(false)}>
            {children}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
