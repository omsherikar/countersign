"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { t } from "@/lib/copy";
import { cn } from "@/lib/utils";

type Step = "pick" | "otp" | "consent";

interface Account {
  role: string;
  digilocker_id: string;
  name: string;
  dob: string;
  apaar_masked: string | null;
  email: string;
}

const button = "inline-flex h-12 w-full items-center justify-center rounded-md border-[1.5px] px-4 text-md font-medium disabled:opacity-60";

/**
 * The mock stand-in for mockgov's Demo DigiLocker (copy deck dldemo.*): pick
 * a synthetic account, type the demo OTP, then allow or deny sharing. Every
 * screen says it is a simulator; nothing here looks like DigiLocker. Allow
 * finishes the sign-in as the api's callback would; Deny returns as
 * cancelled.
 */
export function DemoDigiLocker() {
  const params = useSearchParams();
  const rawNext = params.get("next");
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [step, setStep] = React.useState<Step>("pick");
  const [q, setQ] = React.useState("");
  const [chosen, setChosen] = React.useState<string>("");
  const [otp, setOtp] = React.useState("");
  const [otpError, setOtpError] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const heading = React.useRef<HTMLHeadingElement>(null);

  React.useEffect(() => {
    void import("@/lib/mock/digilocker").then((m) => {
      setAccounts(m.DEMO_ACCOUNTS);
      setChosen(m.DEMO_ACCOUNTS[0].digilocker_id);
    });
  }, []);
  React.useEffect(() => {
    heading.current?.focus();
  }, [step]);

  const account = accounts.find((a) => a.digilocker_id === chosen);
  const needle = q.trim().toUpperCase().replace(/\s+/g, "");
  const shown = accounts.filter((a) => !needle || a.digilocker_id.toUpperCase().includes(needle) || (a.apaar_masked ?? "").replace(/\s+/g, "").endsWith(needle.replace(/^X+/, "")));

  async function finish(allow: boolean) {
    setBusy(true);
    const dl = await import("@/lib/mock/digilocker");
    const next = dl.studentNext(rawNext);
    const back = (path: string) => window.location.assign(path);
    if (!allow || !account) {
      back(`/auth/digilocker/return?error=DIGILOCKER_CANCELLED&next=${encodeURIComponent(next)}`);
      return;
    }
    const session = await import("@/lib/mock/session");
    const loop = await import("@/lib/mock/student-loop");
    if (account.apaar_masked || (account.role === "PROVISIONAL_CLAIM" && loop.ashaClaimed())) {
      dl.writePendingClaim(null);
      session.writeBrowserToken(session.tokenFor(account.email));
      back(`/auth/digilocker/return?next=${encodeURIComponent(next)}`);
      return;
    }
    // No APAAR and not claimed yet: nobody is signed in, a claim waits (A4.12 step 6).
    session.writeBrowserToken(null);
    dl.writePendingClaim({ sub: account.digilocker_id, name: account.name, birthdate: account.dob, next });
    back(dl.isNoticePath(next) ? next : `/student/claim?next=${encodeURIComponent(next)}`);
  }

  const banner = (
    <div className="rounded-md border-2 border-ink px-3 py-2 text-sm">
      <p className="font-semibold">{t("dldemo.title")}</p>
      <p className="mt-1">{t("dldemo.banner")}</p>
    </div>
  );

  return (
    <div className="min-h-dvh bg-paper text-ink">
      <main className="mx-auto flex max-w-[480px] flex-col gap-5 px-4 pt-8 pb-16 text-md">
        {banner}
        {step === "pick" && (
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (account) setStep("otp");
            }}
          >
            <p>{t("dldemo.request")}</p>
            <h1 ref={heading} tabIndex={-1} className="text-2xl outline-none">
              {t("dldemo.pick_heading")}
            </h1>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="dl-search" className="text-sm font-medium">
                {t("dldemo.search_label")}
              </label>
              <input
                id="dl-search"
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="h-12 rounded-md border border-line bg-paper-raised px-3"
                autoComplete="off"
              />
            </div>
            <fieldset>
              <legend className="sr-only">{t("dldemo.pick_heading")}</legend>
              {shown.length === 0 ? (
                <p className="text-ink-muted" role="status">
                  {t("dldemo.search_empty", { q })}
                </p>
              ) : (
                <ul className="flex flex-col divide-y divide-rule rounded-md border border-line bg-paper-raised">
                  {shown.map((a) => (
                    <li key={a.digilocker_id}>
                      <label className={cn("flex min-h-14 cursor-pointer items-center gap-3 px-3 py-2", chosen === a.digilocker_id && "bg-paper-sunken")}>
                        <input type="radio" name="account" value={a.digilocker_id} checked={chosen === a.digilocker_id} onChange={() => setChosen(a.digilocker_id)} className="size-5 shrink-0" />
                        <span>
                          {a.apaar_masked
                            ? t("dldemo.account_line", { name: a.name, apaar_masked: a.apaar_masked })
                            : t("dldemo.account_line_no_apaar", { name: a.name, dl_id_masked: `XXXXXXXXXX${a.digilocker_id.slice(-4)}` })}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </fieldset>
            <button type="submit" disabled={!account} className={cn(button, "border-ink bg-ink text-paper")}>
              {t("dldemo.continue")}
            </button>
          </form>
        )}

        {step === "otp" && (
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (otp.trim() === "123456") {
                setOtpError(false);
                setStep("consent");
              } else {
                setOtpError(true);
                document.getElementById("dl-otp")?.focus();
              }
            }}
          >
            <h1 ref={heading} tabIndex={-1} className="text-2xl outline-none">
              {t("dldemo.otp_heading")}
            </h1>
            <p>{t("dldemo.otp_lead")}</p>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="dl-otp" className="text-sm font-medium">
                {t("dldemo.otp_label")}
              </label>
              <input
                id="dl-otp"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                aria-invalid={otpError || undefined}
                aria-describedby={otpError ? "dl-otp-error" : undefined}
                className="h-12 w-40 rounded-md border border-line bg-paper-raised px-3 font-mono tracking-widest"
              />
              {otpError && (
                <p id="dl-otp-error" className="text-sm text-check-fail-ink">
                  {t("dldemo.otp_wrong")}
                </p>
              )}
            </div>
            <button type="submit" className={cn(button, "border-ink bg-ink text-paper")}>
              {t("dldemo.otp_submit")}
            </button>
            <button type="button" className="inline-flex min-h-11 w-fit items-center underline" onClick={() => setStep("pick")}>
              {t("dldemo.back")}
            </button>
          </form>
        )}

        {step === "consent" && (
          <div className="flex flex-col gap-4">
            <h1 ref={heading} tabIndex={-1} className="text-2xl outline-none">
              {t("dldemo.consent_heading")}
            </h1>
            <p>{t("dldemo.consent_lead")}</p>
            <div className="flex flex-col gap-3">
              <button type="button" disabled={busy} onClick={() => finish(true)} className={cn(button, "border-ink bg-paper-raised")}>
                {t("dldemo.allow")}
              </button>
              <button type="button" disabled={busy} onClick={() => finish(false)} className={cn(button, "border-ink bg-paper-raised")}>
                {t("dldemo.deny")}
              </button>
            </div>
            <button type="button" className="inline-flex min-h-11 w-fit items-center underline" onClick={() => setStep("pick")}>
              {t("dldemo.back")}
            </button>
          </div>
        )}

        <p className="border-t border-rule pt-4 text-sm text-ink-muted">{t("dldemo.footer")}</p>
      </main>
    </div>
  );
}
