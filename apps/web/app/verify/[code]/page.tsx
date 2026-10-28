import type { Metadata } from "next";
import { t } from "@/lib/copy";
import { VerifyCodePage } from "@/components/verify/verify-pages";

export const metadata: Metadata = { title: t("verify.result_title"), robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function VerifyCode({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  return <VerifyCodePage code={decodeURIComponent(code)} />;
}
