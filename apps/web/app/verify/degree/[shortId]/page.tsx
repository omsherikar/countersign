import type { Metadata } from "next";
import { t } from "@/lib/copy";
import { VerifyLookupPage } from "@/components/verify/verify-pages";

export const metadata: Metadata = { title: t("verify.result_title"), robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function VerifyLookup({ params }: { params: Promise<{ shortId: string }> }) {
  const { shortId } = await params;
  return <VerifyLookupPage shortId={decodeURIComponent(shortId)} />;
}
