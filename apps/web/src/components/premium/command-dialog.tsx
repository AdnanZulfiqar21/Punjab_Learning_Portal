"use client";
// PREMIUM-LOOK-01: the Ctrl K dialog itself (cmdk in a Radix dialog), loaded on first open by CommandSearch.
import { Command } from "cmdk";
import { Dialog } from "radix-ui";
import { CornerDownLeft, Search } from "lucide-react";
import { useRouter } from "next/navigation";

export type SearchItem = { id: string; label: string; group: string };

const HEADING =
  "[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-muted";

export function CommandDialog({
  open,
  onOpenChange,
  items,
  base,
  placeholder,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  items: SearchItem[];
  base: string;
  placeholder: string;
}) {
  const router = useRouter();
  const groups = [...new Set(items.map((i) => i.group))];
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" />
        <Dialog.Content className="dialog-content fixed top-[12vh] left-1/2 z-50 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-3xl border border-border bg-surface shadow-2xl">
          <Dialog.Title className="sr-only">Search this chapter</Dialog.Title>
          <Dialog.Description className="sr-only">Type part of a topic&apos;s name, then choose it to open it.</Dialog.Description>
          <Command label="Search this chapter" className="flex flex-col">
            <div className="flex items-center gap-2 border-b border-border px-4">
              <Search size={18} className="text-muted" aria-hidden />
              <Command.Input autoFocus placeholder={placeholder} className="min-h-14 flex-1 bg-transparent text-[16px] outline-none placeholder:text-muted" />
            </div>
            <Command.List className="max-h-[55vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-8 text-center text-sm text-muted">Nothing matches.</Command.Empty>
              {groups.map((g) => (
                <Command.Group key={g} heading={g} className={HEADING}>
                  {items
                    .filter((i) => i.group === g)
                    .map((i) => (
                      <Command.Item
                        key={i.id}
                        value={`${i.label} ${i.group} ${i.id}`}
                        onSelect={() => {
                          onOpenChange(false);
                          router.push(`${base}/${i.id}`);
                        }}
                        className="flex min-h-11 cursor-pointer items-center gap-2 rounded-xl px-3 text-[15px] data-[selected=true]:bg-accent-soft data-[selected=true]:text-accent"
                      >
                        <span className="flex-1">{i.label}</span>
                        <CornerDownLeft size={14} className="opacity-50" aria-hidden />
                      </Command.Item>
                    ))}
                </Command.Group>
              ))}
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
