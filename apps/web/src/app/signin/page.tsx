import type { Metadata } from "next";
import { Suspense } from "react";
import { Notice, SkeletonLines } from "@/components/ui";
import { signInMethods } from "@/lib/session";
import { DevPasswordForm } from "./sign-in-form";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

export default function SignInPage({ searchParams }: PageProps<"/signin">) {
  return (
    <div className="mx-auto max-w-md space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <Suspense fallback={<SkeletonLines lines={4} label="Loading sign-in options" />}>
        {searchParams.then((sp) => (
          <Methods next={typeof sp.next === "string" ? sp.next : "/account"} />
        ))}
      </Suspense>
    </div>
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
