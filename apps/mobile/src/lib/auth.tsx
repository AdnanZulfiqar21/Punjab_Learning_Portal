// Learner authentication state for the app. The session token is read from secure storage once at start-up and
// validated against the API; a 401 anywhere means the session ended (expired, revoked elsewhere) and clears it.
import * as Device from "expo-device";
import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Me } from "@portal/contracts";

import { api, ApiError } from "@/lib/api";
import { tokenStore } from "@/lib/token-store";

export type AuthState =
  | { status: "loading" }
  | { status: "signed_out" }
  | { status: "unavailable"; error: ApiError }
  | { status: "signed_in"; token: string; me: Me };

type AuthContextValue = {
  state: AuthState;
  signIn: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
  /** Call when an authenticated request fails; ends the local session on 401. */
  handleError: (e: unknown) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function deviceLabel(): string {
  const name = [Device.manufacturer, Device.modelName].filter(Boolean).join(" ");
  return name || "Mobile app";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const load = useCallback(async (token: string | null) => {
    if (!token) {
      setState({ status: "signed_out" });
      return;
    }
    try {
      setState({ status: "signed_in", token, me: await api.me(token) });
    } catch (e) {
      if (e instanceof ApiError && e.kind === "unauthorized") {
        await tokenStore.clear();
        setState({ status: "signed_out" });
      } else {
        // Offline or server trouble: keep the stored session and let the screen offer a retry.
        setState({ status: "unavailable", error: e instanceof ApiError ? e : new ApiError("Something went wrong.", "server") });
      }
    }
  }, []);

  useEffect(() => {
    tokenStore.get().then(load, () => setState({ status: "signed_out" }));
  }, [load]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await api.devToken(email, password);
      const created = await api.createSession(access_token, deviceLabel());
      await tokenStore.set(created.session_token);
      await load(created.session_token);
    },
    [load],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      await api.devRegister(email, password);
      await signIn(email, password);
    },
    [signIn],
  );

  const signOut = useCallback(async () => {
    const token = await tokenStore.get();
    if (token) await api.signOut(token).catch(() => undefined); // local sign-out must succeed even offline
    await tokenStore.clear();
    setState({ status: "signed_out" });
  }, []);

  const refresh = useCallback(async () => load(await tokenStore.get()), [load]);

  const handleError = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.kind === "unauthorized") {
      void tokenStore.clear();
      setState({ status: "signed_out" });
    }
  }, []);

  const value = useMemo(
    () => ({ state, signIn, register, signOut, refresh, handleError }),
    [state, signIn, register, signOut, refresh, handleError],
  );
  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const ctx = use(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
