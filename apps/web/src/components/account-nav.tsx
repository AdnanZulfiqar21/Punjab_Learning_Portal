import Link from "next/link";
import { sessionToken } from "@/lib/session";

// Reads only cookie presence (no API call) so the header never waits on the network; the account page validates it.
export async function AccountNav() {
  const signedIn = Boolean(await sessionToken());
  return (
    <Link
      href={signedIn ? "/account" : "/signin"}
      className="rounded-md px-3 py-2 text-muted hover:bg-surface-muted hover:text-foreground"
    >
      {signedIn ? "Account" : "Sign in"}
    </Link>
  );
}
