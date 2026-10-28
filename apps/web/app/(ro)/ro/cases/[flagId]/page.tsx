import type { Metadata } from "next";
import { Suspense } from "react";
import { FlagDetail } from "@/components/flags/flag-detail";

export const metadata: Metadata = { title: "Flag" };

export default async function Case({ params }: { params: Promise<{ flagId: string }> }) {
  const { flagId } = await params;
  return (
    <Suspense>
      <FlagDetail id={flagId} variant="ro" />
    </Suspense>
  );
}
