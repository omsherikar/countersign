import type { Metadata } from "next";
import { t } from "@/lib/copy";
import { DegreePrintPage } from "@/components/university/degree-print";

export const metadata: Metadata = { title: t("degree.heading") };

export default async function DegreePrint({ params }: { params: Promise<{ enrolmentId: string }> }) {
  const { enrolmentId } = await params;
  return <DegreePrintPage enrolmentId={enrolmentId} />;
}
