import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getMe } from "@/lib/auth";
import { t } from "@/lib/copy";
import { landingFor } from "@/lib/roles";
import { LoginForm } from "@/components/auth/login-form";
import { Logo } from "@/components/shell/logo";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; expired?: string; signed_out?: string }>;
}) {
  const params = await searchParams;
  const me = await getMe();
  if (me) redirect(landingFor(me.role));
  const notice = params.expired ? t("err.UNAUTHENTICATED") : params.signed_out ? t("login.signed_out") : null;
  return (
    <div className="min-h-dvh bg-paper">
      <header className="border-b border-rule-strong bg-paper-raised">
        <div className="mx-auto flex h-14 max-w-[760px] items-center justify-between gap-4 px-4">
          <Logo className="h-7" />
          <p className="hidden font-display text-md text-ink-muted italic sm:block">{t("brand.tagline")}</p>
        </div>
      </header>
      <main className="mx-auto max-w-[760px] px-4 pt-10 pb-16">
        <h1 className="text-3xl">{t("login.heading")}</h1>
        <p className="mt-1.5 mb-8 text-md text-ink-muted">{t("login.sub")}</p>
        <LoginForm next={params.next ?? null} notice={notice} />
        <p className="mt-8 text-sm text-ink-muted">{t("login.demo_footer")}</p>
      </main>
    </div>
  );
}
