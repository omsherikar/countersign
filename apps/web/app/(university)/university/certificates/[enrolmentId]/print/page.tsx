import type { Metadata } from "next";
import { t } from "@/lib/copy";
import { CertificatePrintPage } from "@/components/university/certificate-print";

export const metadata: Metadata = { title: t("cert.heading") };

export default async function CertificatePrint({ params }: { params: Promise<{ enrolmentId: string }> }) {
  const { enrolmentId } = await params;
  return <CertificatePrintPage enrolmentId={enrolmentId} />;
}
