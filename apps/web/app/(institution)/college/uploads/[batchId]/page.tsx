import type { Metadata } from "next";
import { Suspense } from "react";
import { BatchPage } from "@/components/uploads/batch-page";

export const metadata: Metadata = { title: "Upload" };

export default async function CollegeUploadBatch({ params }: { params: Promise<{ batchId: string }> }) {
  const { batchId } = await params;
  return (
    <Suspense>
      <BatchPage id={batchId} />
    </Suspense>
  );
}
