import Link from "next/link";

export default function NotFound() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">This page isn’t available</h1>
      <p className="text-muted">
        The class, subject or chapter you asked for isn’t in the portal. The portal currently covers Class XI and Class XII
        Biology, Chemistry, Physics, Computer Science and Mathematics.
      </p>
      <Link href="/learn" className="inline-block rounded-lg border border-border bg-surface px-4 py-2 hover:border-accent">
        Browse all chapters
      </Link>
    </div>
  );
}
