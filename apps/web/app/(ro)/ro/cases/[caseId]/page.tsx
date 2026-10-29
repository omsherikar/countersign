import type { Metadata } from "next";
import { Suspense } from "react";
import { FlagDetail } from "@/components/flags/flag-detail";

export const metadata: Metadata = { title: "Case" };

export default async function Case({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return (
    <Suspense>
      <FlagDetail id={caseId} variant="ro" />
    </Suspense>
  );
}
