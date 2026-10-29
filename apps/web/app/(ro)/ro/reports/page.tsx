import type { Metadata } from "next";
import { Suspense } from "react";
import { ReportsPage } from "@/components/reports/reports-page";

export const metadata: Metadata = { title: "Reports" };

export default function Reports() {
  return (
    <Suspense>
      <ReportsPage variant="ro" />
    </Suspense>
  );
}
