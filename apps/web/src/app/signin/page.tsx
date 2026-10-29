import type { Metadata } from "next";
import { Suspense } from "react";
import { CenteredCard } from "@/components/learner-pages";
import { Notice, SkeletonLines } from "@/components/ui";
import { signInMethods } from "@/lib/session";
import { DevPasswordForm } from "./sign-in-form";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

export default function SignInPage({ searchParams }: PageProps<"/signin">) {
  return (
    <CenteredCard icon="user" title="Sign in" lead="Sign in to keep your place in each book and to practise. A new account can start the free 30-day trial.">
      <Suspense fallback={<SkeletonLines lines={4} label="Loading sign-in options" />}>
        {searchParams.then((sp) => (
          <div className="space-y-4">
            {sp.reason === "reauth" && (
              // P04.S3.T3 (REAUTH-01): downloading your data or asking to delete your account needs a recent sign-in.
              <Notice title="Sign in again to continue">For your safety, this needs a recent sign-in. You&apos;ll go straight back afterwards.</Notice>
            )}
            <Methods next={typeof sp.next === "string" ? sp.next : "/account"} />
          </div>
        ))}
      </Suspense>
    </CenteredCard>
  );
}

async function Methods({ next }: { next: string }) {
  const methods = await signInMethods();
  if (methods.includes("dev_password")) {
    return (
      <div className="space-y-4">
        <Notice tone="warn" title="Development sign-in">
          This environment uses a local development identity service. Real accounts will sign in through the managed
          identity provider.
        </Notice>
        <DevPasswordForm next={next} />
      </div>
    );
  }
  if (methods.includes("oidc")) {
    return (
      <Notice title="Sign-in provider not yet connected">
        Provider sign-in for this environment is configured on the server but the web redirect flow is not enabled yet.
      </Notice>
    );
  }
  return <Notice tone="warn" title="Sign-in is not available in this environment" />;
}
