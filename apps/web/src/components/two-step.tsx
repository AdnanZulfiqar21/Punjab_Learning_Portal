"use client";

import { useState, useTransition } from "react";
import type { MfaEnrolment, MfaStatus } from "@portal/contracts";
import { confirmTwoStep, startTwoStep, turnOffTwoStep, verifyTwoStep } from "@/app/actions/mfa";
import { Button } from "@/components/button";

const INPUT = "w-full max-w-56 rounded-lg border border-border bg-surface px-3 py-2 font-mono tracking-widest";

function CodeField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={20}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={INPUT}
      />
    </div>
  );
}

/** STAFF-MFA-01: set up an authenticator app, enter its code on this device (it lasts twelve hours), or turn it off.
 * Every rule is the API's; this only shows the steps. */
export function TwoStep({ status }: { status: MfaStatus }) {
  const [state, setState] = useState(status);
  const [setup, setSetup] = useState<MfaEnrolment | null>(null);
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [code, setCode] = useState("");
  const [turningOff, setTurningOff] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const run = (work: () => Promise<void>) =>
    start(async () => {
      setError(null);
      await work();
    });

  if (recovery) {
    return (
      <div className="space-y-3">
        <p role="status" className="font-medium">
          Two-step sign-in is on.
        </p>
        <p className="text-sm text-muted">
          Keep these recovery codes somewhere safe. Each one works once, in place of a code, if you lose your phone. They are shown only now.
        </p>
        <ul className="grid max-w-md grid-cols-2 gap-2 rounded-inner border border-border bg-surface p-3 font-mono text-sm">
          {recovery.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        <Button variant="secondary" onClick={() => setRecovery(null)}>
          I have saved them
        </Button>
      </div>
    );
  }

  if (!state.enabled) {
    if (!setup) {
      return (
        <div className="space-y-3">
          <p className="text-sm text-muted">
            Off. Staff actions such as publishing, roles and finance need it. You need an authenticator app on your phone (Google Authenticator, Microsoft
            Authenticator or a similar one).
          </p>
          <Button
            disabled={pending}
            onClick={() =>
              run(async () => {
                const res = await startTwoStep();
                if (res.ok) setSetup(res.data);
                else setError(res.message);
              })
            }
          >
            {pending ? "Starting…" : "Set up two-step sign-in"}
          </Button>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
        </div>
      );
    }
    return (
      <div className="space-y-3">
        <ol className="list-decimal space-y-2 pl-5 text-sm">
          <li>
            In your authenticator app, add an account and choose to enter a setup key. On a phone you can{" "}
            <a href={setup.otpauth_uri} className="font-medium text-accent underline">
              open the app directly
            </a>
            .
          </li>
          <li>
            Type this key: <span className="rounded bg-surface px-2 py-1 font-mono font-semibold tracking-wider break-all">{setup.secret}</span>
          </li>
          <li>Enter the 6-digit code the app shows.</li>
        </ol>
        <CodeField id="two-step-first-code" label="Code from the app" value={code} onChange={setCode} />
        <Button
          disabled={pending || code.trim().length < 6}
          onClick={() =>
            run(async () => {
              const res = await confirmTwoStep(code.trim());
              if (res.ok) {
                setRecovery(res.data);
                setState({ enabled: true, session_verified: true, recovery_codes_left: res.data.length });
                setSetup(null);
                setCode("");
              } else setError(res.message);
            })
          }
        >
          {pending ? "Checking…" : "Turn on"}
        </Button>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm">
        <span className="font-medium">On.</span>{" "}
        {state.session_verified
          ? "This device has entered a code. It is asked for again after twelve hours."
          : "Enter a code to use staff actions on this device. It lasts twelve hours."}{" "}
        <span className="text-muted">Recovery codes left: {state.recovery_codes_left}.</span>
      </p>
      {(!state.session_verified || turningOff) && (
        <CodeField
          id="two-step-code"
          label={turningOff ? "Code (or a recovery code) to turn it off" : "Code from the app (or a recovery code)"}
          value={code}
          onChange={setCode}
        />
      )}
      <div className="flex flex-wrap gap-3">
        {!state.session_verified && !turningOff && (
          <Button
            disabled={pending || code.trim().length < 6}
            onClick={() =>
              run(async () => {
                const res = await verifyTwoStep(code.trim());
                if (res.ok) {
                  setState(res.data);
                  setCode("");
                } else setError(res.message);
              })
            }
          >
            {pending ? "Checking…" : "Confirm code"}
          </Button>
        )}
        {turningOff ? (
          <>
            <Button
              variant="secondary"
              disabled={pending || code.trim().length < 6}
              onClick={() =>
                run(async () => {
                  const res = await turnOffTwoStep(code.trim());
                  if (res.ok) {
                    setState({ enabled: false, session_verified: false, recovery_codes_left: 0 });
                    setTurningOff(false);
                    setCode("");
                  } else setError(res.message);
                })
              }
            >
              {pending ? "Turning off…" : "Turn off two-step sign-in"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setTurningOff(false);
                setCode("");
                setError(null);
              }}
            >
              Cancel
            </Button>
          </>
        ) : (
          <Button
            variant="secondary"
            onClick={() => {
              setTurningOff(true);
              setCode("");
              setError(null);
            }}
          >
            Turn off…
          </Button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
