import { sessionToken } from "@/lib/session";
import { AccountLink } from "./site-nav";

// Reads only cookie presence (no API call) so the header never waits on the network; the account page validates it.
// DESIGN-01: the link itself is a client component so it can mark itself when an account page is open.
export async function AccountNav() {
  const signedIn = Boolean(await sessionToken());
  return <AccountLink signedIn={signedIn} />;
}
