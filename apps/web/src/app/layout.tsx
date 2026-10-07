import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import { AccountNav } from "@/components/account-nav";
import "./globals.css";

const sans = Geist({ variable: "--font-sans-ui", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-mono-ui", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Punjab Learning Portal", template: "%s · Punjab Learning Portal" },
  description:
    "Class XI and Class XII Biology, Chemistry, Physics, Computer Science and Mathematics for Punjab, organised by the official textbooks.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f8fa" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1318" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <header className="border-b border-border bg-surface">
          <nav
            aria-label="Main"
            className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-3"
          >
            <Link href="/" className="font-semibold tracking-tight text-foreground">
              Punjab Learning Portal
            </Link>
            <ul className="flex items-center gap-1 text-sm">
              <li>
                <Link href="/learn" className="rounded-md px-3 py-2 text-muted hover:bg-surface-muted hover:text-foreground">
                  Learn
                </Link>
              </li>
              <li>
                <Link href="/search" className="rounded-md px-3 py-2 text-muted hover:bg-surface-muted hover:text-foreground">
                  Search
                </Link>
              </li>
              <li>
                <Suspense fallback={<span className="px-3 py-2 text-muted">&nbsp;</span>}>
                  <AccountNav />
                </Suspense>
              </li>
            </ul>
          </nav>
        </header>
        <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
          {children}
        </main>
        <footer className="border-t border-border bg-surface">
          <p className="mx-auto max-w-5xl px-4 py-5 text-sm text-muted">
            Organised by the official Punjab Class XI and XII textbooks. Lessons, videos and tests are published only after
            academic review.
          </p>
        </footer>
      </body>
    </html>
  );
}
