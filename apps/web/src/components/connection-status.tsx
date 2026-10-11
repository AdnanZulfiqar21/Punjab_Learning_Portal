"use client";

// P11.S4.T2 (PWA-01): registers the offline-shell service worker (production builds only; it caches nothing but the
// offline page) and says when the connection drops or returns.
import { useEffect, useState } from "react";

export function ConnectionStatus() {
  const [state, setState] = useState<"online" | "offline" | "back">("online");

  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => undefined);
    }
    let timer: ReturnType<typeof setTimeout> | undefined;
    const offline = () => setState("offline");
    const online = () => {
      setState("back");
      timer = setTimeout(() => setState("online"), 4000);
    };
    if (!navigator.onLine) offline();
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    return () => {
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (state === "online") return null;
  return (
    <div role="status" className={`border-b px-4 py-2 text-center text-sm ${state === "offline" ? "border-warn bg-warn-soft" : "border-ok bg-ok-soft"}`}>
      {state === "offline"
        ? "You're offline. Pages need a connection; answers you choose in a test are kept on this device and sent when you're back."
        : "You're back online."}
    </div>
  );
}
