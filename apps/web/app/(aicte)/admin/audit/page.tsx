import type { Metadata } from "next";
import { Suspense } from "react";
import { AuditPage } from "@/components/admin/audit-page";

export const metadata: Metadata = { title: "Audit" };

export default function AdminAudit() {
  return (
    <Suspense>
      <AuditPage />
    </Suspense>
  );
}
