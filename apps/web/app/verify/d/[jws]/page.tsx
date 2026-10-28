import type { Metadata } from "next";
import { t } from "@/lib/copy";
import { VerifyDegreePage } from "@/components/verify/verify-pages";

export const metadata: Metadata = { title: t("verify.result_title"), robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function VerifyDegree({ params }: { params: Promise<{ jws: string }> }) {
  const { jws } = await params;
  return <VerifyDegreePage jws={jws} />;
}
