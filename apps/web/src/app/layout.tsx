import type { Metadata, Viewport } from "next";
import { Geist_Mono, Inter, Noto_Nastaliq_Urdu, Outfit } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import { AccountNav } from "@/components/account-nav";
import { ConnectionStatus } from "@/components/connection-status";
import { DisplaySync } from "@/components/display-sync";
import { IncidentBanner } from "@/components/incident-banner";
import { SiteNav, SiteNavFallback } from "@/components/site-nav";
import { DISPLAY_SCRIPT } from "@/lib/display";
import "./globals.css";

// DESIGN-01 (draft C · Soft Glass): Inter for body and UI, Outfit for headings, display and the brand. next/font
// self-hosts both (served from this site, so the CSP's font-src 'self' holds; no request goes to Google).
const sans = Inter({ variable: "--font-sans-ui", subsets: ["latin"] });
const heading = Outfit({ variable: "--font-heading", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-mono-ui", subsets: ["latin"] });
// P02.S2.T1 (TOKENS-01): Urdu is set in Nastaliq, the style Punjab's Urdu textbooks use (Noto Nastaliq Urdu, SIL Open
// Font Licence). Not preloaded: only pages that show Urdu text fetch it, so English pages carry no extra weight.
const urdu = Noto_Nastaliq_Urdu({ variable: "--font-urdu", subsets: ["arabic"], weight: "variable", preload: false });

export const metadata: Metadata = {
  title: { default: "Punjab Learning Portal", template: "%s · Punjab Learning Portal" },
  description:
    "Class 11 and Class 12 Biology, Chemistry, Physics, Computer Science and Mathematics for Punjab, organised by the official textbooks.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8f6f2" },
    { media: "(prefers-color-scheme: dark)", color: "#121412" },
  ],
};

const FOOTER_LINKS = [
  ["/learn", "Learn"],
  ["/practice", "Practice"],
  ["/help", "Help"],
  ["/pricing", "Pricing"],
] as const;

/** The Account / Sign in link reads the session cookie, so it streams in on its own. */
function AccountSlot() {
  return (
    <Suspense fallback={<span className="inline-block min-h-11 w-16" aria-hidden="true" />}>
      <AccountNav />
    </Suspense>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The display script sets this device's theme, text size and motion on <html> before the first paint (SETTINGS-01).
    <html lang="en" className={`${sans.variable} ${heading.variable} ${mono.variable} ${urdu.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: DISPLAY_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <ConnectionStatus />
        <Suspense fallback={null}>
          <DisplaySync />
        </Suspense>
        {/* DESIGN-01: a floating glass header inside the page container (globals.css .site-header keeps it in view). */}
        <header className="site-header mx-auto mt-3 w-full max-w-6xl px-4">
          <div className="glass relative flex items-center justify-between gap-2 rounded-card py-2 pr-2 pl-4 sm:px-5">
            <Link href="/" className="min-w-0 font-display text-base leading-tight font-bold tracking-tight text-foreground sm:text-lg">
              Punjab Learning Portal
            </Link>
            <Suspense fallback={<SiteNavFallback account={<AccountSlot />} />}>
              <SiteNav account={<AccountSlot />} />
            </Suspense>
          </div>
        </header>
        <Suspense fallback={null}>
          <IncidentBanner />
        </Suspense>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
          {children}
        </main>
        {/* DESIGN-01: a centred muted line on the mesh. */}
        <footer className="mx-auto w-full max-w-6xl px-4 pt-4 pb-10 text-center text-sm text-muted">
          <nav aria-label="Footer">
          <ul className="mb-2 flex flex-wrap justify-center gap-x-1">
            {FOOTER_LINKS.map(([href, label], i) => (
              <li key={href} className="flex items-center gap-x-1">
                {i > 0 && <span aria-hidden="true">·</span>}
                <Link href={href} className="inline-flex min-h-11 items-center px-2 font-medium hover:text-accent">
                  {label}
                </Link>
              </li>
            ))}
          </ul>
          </nav>
          <p className="mx-auto max-w-2xl">
            Organised by the official Punjab Class 11 and 12 textbooks. Lessons, videos and tests are published only after
            academic review.
          </p>
        </footer>
      </body>
    </html>
  );
}
