import type { Metadata } from "next";
import { Suspense } from "react";
import { UniversityPage } from "@/components/overview/university-page";

export const metadata: Metadata = { title: "Affiliated institutions" };

export default function University() {
  return (
    <Suspense>
      <UniversityPage />
    </Suspense>
  );
}
