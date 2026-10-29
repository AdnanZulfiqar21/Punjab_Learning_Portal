"use client";

// DESIGN-01: the header's links with the current section marked (accent colour and aria-current). Below `sm` the
// section links fold behind a menu button; the Account link stays in view. The menu is a disclosure: the button says
// whether it is open (aria-expanded), Escape closes it and returns focus to the button, and following a link closes it.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { activeSection, NAV_ITEMS, type Section } from "@/lib/nav";
import { Icon } from "./icons";

const LINK =
  "flex min-h-11 items-center rounded-full text-[15px] font-semibold transition-colors duration-200 hover:bg-surface-muted hover:text-foreground";

// "page" on the section's own page, "true" on a page inside it (a book under Learn).
const currentKind = (pathname: string | null, href: string) => (pathname === href ? "page" : "true");

/** The header navigation for the current page. */
export function SiteNav({ account }: { account: ReactNode }) {
  const pathname = usePathname();
  return <NavBar active={activeSection(pathname)} pathname={pathname} account={account} />;
}

/** Shown while the pathname is not known yet (prerendering a page whose path depends on the request). */
export function SiteNavFallback({ account }: { account: ReactNode }) {
  return <NavBar active={null} pathname={null} account={account} />;
}

function NavBar({ active, pathname, account }: { active: Section | null; pathname: string | null; account: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [lastActive, setLastActive] = useState(active);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  // A route change (a link was followed) closes the menu; adjusting state during render, not in an effect.
  if (lastActive !== active) {
    setLastActive(active);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <nav aria-label="Main" className="flex items-center gap-1">
      {/* First in reading order, so Tab goes from the button into the links it opened. */}
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((o) => !o)}
        className="order-last inline-flex size-11 items-center justify-center rounded-full text-foreground hover:bg-surface-muted sm:hidden"
      >
        <Icon name={open ? "x" : "menu"} size={22} />
        <span className="sr-only">Menu</span>
      </button>
      <ul
        id={menuId}
        className={`${open ? "flex" : "hidden"} absolute inset-x-0 top-full mt-2 flex-col gap-1 p-2 max-sm:glass max-sm:rounded-card sm:static sm:mt-0 sm:flex sm:flex-row sm:items-center sm:gap-0.5 sm:p-0`}
      >
        {NAV_ITEMS.map((item) => {
          const current = active === item.key;
          return (
            <li key={item.key}>
              <Link
                href={item.href}
                aria-current={current ? currentKind(pathname, item.href) : undefined}
                onClick={() => setOpen(false)}
                className={`${LINK} px-3 ${current ? "text-accent" : "text-muted"}`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
      {account}
    </nav>
  );
}

/** The Account / Sign in link (components/account-nav.tsx decides which), marked when an account page is open. */
export function AccountLink({ signedIn }: { signedIn: boolean }) {
  const current = activeSection(usePathname()) === "account";
  return (
    <Link
      href={signedIn ? "/account" : "/signin"}
      aria-current={current ? "true" : undefined}
      className={`${LINK} px-2 sm:px-3 ${current ? "text-accent" : "text-muted"}`}
    >
      {signedIn ? "Account" : "Sign in"}
    </Link>
  );
}
