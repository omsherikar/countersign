import type { Metadata } from "next";
import { Suspense } from "react";
import { DataRequestsPage } from "@/components/admin/data-requests-page";

export const metadata: Metadata = { title: "Data requests" };

export default function AdminDataRequests() {
  return (
    <Suspense>
      <DataRequestsPage />
    </Suspense>
  );
}
