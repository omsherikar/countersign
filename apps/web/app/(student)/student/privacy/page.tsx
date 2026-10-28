import type { Metadata } from "next";
import { PrivacyPage } from "@/components/student/privacy-page";
import { t } from "@/lib/copy";

export const metadata: Metadata = { title: t("privacy.heading") };

export default function Privacy() {
  return <PrivacyPage />;
}
