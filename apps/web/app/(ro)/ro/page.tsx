import type { Metadata } from "next";
import { Suspense } from "react";
import { OverviewPage } from "@/components/overview/overview-page";

export const metadata: Metadata = { title: "Overview" };

export default function RegionalOverview() {
  return (
    <Suspense>
      <OverviewPage variant="ro" />
    </Suspense>
  );
}
