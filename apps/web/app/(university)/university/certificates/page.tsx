import type { Metadata } from "next";
import { Suspense } from "react";
import { t } from "@/lib/copy";
import { CertificatesPage } from "@/components/university/certificates-page";

export const metadata: Metadata = { title: t("cert.heading") };

export default function Certificates() {
  return (
    <Suspense>
      <CertificatesPage />
    </Suspense>
  );
}
