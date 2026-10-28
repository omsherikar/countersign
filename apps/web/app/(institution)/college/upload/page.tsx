import type { Metadata } from "next";
import { Suspense } from "react";
import { UploadPage } from "@/components/uploads/upload-page";

export const metadata: Metadata = { title: "Upload" };

export default function CollegeUploadPage() {
  return (
    <Suspense>
      <UploadPage />
    </Suspense>
  );
}
