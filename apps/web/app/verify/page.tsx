import type { Metadata } from "next";
import { t } from "@/lib/copy";
import { VerifyEntry } from "@/components/verify/verify-pages";

export const metadata: Metadata = { title: t("verify.bar") };

export default function VerifyPage() {
  return <VerifyEntry />;
}
