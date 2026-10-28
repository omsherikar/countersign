import Link from "next/link";
import { t } from "@/lib/copy";
import { Logo } from "@/components/shell/logo";

/** Public verifier pages (W3-4): the mark and "Verify a proof", no nav, no search, no sign-in. */
export default function VerifyLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-paper">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-paper-raised focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="border-b border-rule-strong bg-paper-raised">
        <div className="mx-auto flex h-14 max-w-[480px] items-center justify-between gap-3 px-4">
          <Link href="/verify" className="no-underline" aria-label={`${t("brand.name")}, ${t("verify.bar")}`}>
            <Logo className="h-7" />
          </Link>
          <span className="text-sm text-ink-muted">{t("verify.bar")}</span>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-[480px] px-4 pt-8 pb-16 text-md">
        {children}
      </main>
    </div>
  );
}
