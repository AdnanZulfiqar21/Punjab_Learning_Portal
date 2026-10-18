// Learner preferences as React context (pilot): the Learn tab's class and group chosen on this device, and the reader
// language. A signed-in learner's profile still wins for class and group (see learn-context-core.ts); this is what a
// guest chose, or what fills in while the profile is incomplete. Free of API imports so screens can read it anywhere.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { parseStored, type LearnContext } from "@/lib/learn-context-core";
import { readPrefsRaw, writePrefsRaw } from "@/lib/prefs-store";
import { isReadingLanguage, type ReadingLanguage } from "@/lib/reading-language-core";

export type Prefs = { context: Partial<LearnContext> | null; language: ReadingLanguage | null };

const EMPTY: Prefs = { context: null, language: null };

type Ctx = { prefs: Prefs; loaded: boolean; update: (patch: Partial<Prefs>) => void };
const PrefsContext = createContext<Ctx>({ prefs: EMPTY, loaded: false, update: () => {} });

function parse(raw: unknown): Prefs {
  if (!raw || typeof raw !== "object") return EMPTY;
  const r = raw as Record<string, unknown>;
  return { context: parseStored(r.context), language: isReadingLanguage(r.language) ? r.language : null };
}

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(EMPTY);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    readPrefsRaw().then((raw) => {
      setPrefs(parse(raw));
      setLoaded(true);
    });
  }, []);

  const update = useCallback((patch: Partial<Prefs>) => {
    setPrefs((current) => {
      const next = { ...current, ...patch };
      void writePrefsRaw(next);
      return next;
    });
  }, []);

  const value = useMemo(() => ({ prefs, loaded, update }), [prefs, loaded, update]);
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): Ctx {
  return useContext(PrefsContext);
}
