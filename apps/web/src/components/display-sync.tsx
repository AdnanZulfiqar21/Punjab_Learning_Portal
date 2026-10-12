"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { readDisplay, showDisplay } from "@/lib/display";

// SETTINGS-01: the display script only runs on a full page load. Signing in sets this device's display cookie and then
// navigates within the app, so the choice is shown again after each navigation.
export function DisplaySync() {
  const pathname = usePathname();
  useEffect(() => {
    const d = readDisplay();
    if (d) showDisplay(d);
  }, [pathname]);
  return null;
}
