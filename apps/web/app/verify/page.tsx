import type { Metadata } from "next";
import Link from "next/link";
import { Camera } from "lucide-react";
import { t } from "@/lib/copy";
import { Logo } from "@/components/shell/logo";

export const metadata: Metadata = { title: t("app.verify.bar") };

/**
 * Public verifier shell. Week 1 accepts nothing: the scan button and the
 * code box are visibly disabled and say why. No login, no nav, no search.
 */
export default function VerifyPage() {
  return (
    <div className="min-h-dvh bg-paper">
      <header className="border-b border-rule-strong bg-paper-raised">
        <div className="mx-auto flex h-14 max-w-[480px] items-center justify-between gap-3 px-4">
          <Link href="/verify" className="no-underline" aria-label={t("brand.name")}>
            <Logo className="h-7" />
          </Link>
          <span className="text-sm text-ink-muted">{t("app.verify.bar")}</span>
        </div>
      </header>
      <main className="mx-auto max-w-[480px] px-4 pt-10 pb-16 text-md">
        <h1 className="text-2xl">{t("verify.heading")}</h1>
        <p className="mt-2 text-ink-muted">{t("verify.lead")}</p>

        <div className="mt-8 flex flex-col gap-5 border-l-2 border-rule-margin bg-paper-raised px-5 py-5 shadow-hairline">
          <button
            type="button"
            aria-disabled="true"
            aria-describedby="verify-coming"
            className="inline-flex h-11 cursor-not-allowed items-center justify-center gap-2 rounded-md border border-line bg-paper px-4 font-medium text-ink-faint"
          >
            <Camera className="size-4" aria-hidden="true" />
            {t("verify.scan")}
          </button>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="code" className="text-sm font-medium">
              {t("verify.code_label")}
            </label>
            <div className="flex gap-2">
              <input
                id="code"
                type="text"
                inputMode="text"
                autoComplete="off"
                placeholder={t("verify.placeholder")}
                aria-disabled="true"
                aria-describedby="verify-coming"
                readOnly
                className="code h-11 min-w-0 flex-1 cursor-not-allowed rounded-md border border-line bg-paper px-3 text-md text-ink-faint"
              />
              <button
                type="button"
                aria-disabled="true"
                aria-describedby="verify-coming"
                className="h-11 cursor-not-allowed rounded-md border border-line bg-paper px-4 font-medium text-ink-faint"
              >
                {t("verify.check")}
              </button>
            </div>
          </div>
          <p id="verify-coming" className="text-sm text-check-pending-ink">
            {t("verify.coming")}
          </p>
        </div>

        <p className="mt-8 text-ink-muted">{t("verify.what")}</p>
        <p className="mt-3 text-sm">
          <a href="#about">{t("verify.about_link")}</a>
        </p>

        <section id="about" className="mt-10 border-t border-rule pt-5">
          <h2 className="font-sans text-md font-semibold">{t("verify.about_link")}</h2>
          <p className="mt-2 text-sm text-ink-muted">{t("app.verify.what_is")}</p>
        </section>
      </main>
    </div>
  );
}
