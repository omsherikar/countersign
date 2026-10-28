import type { Metadata } from "next";
import { NoticesPage } from "@/components/student/notices-page";
import { t } from "@/lib/copy";

export const metadata: Metadata = { title: t("notices.heading") };

export default function Notices() {
  return <NoticesPage />;
}
