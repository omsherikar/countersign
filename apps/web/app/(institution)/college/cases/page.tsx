import type { Metadata } from "next";
import { Suspense } from "react";
import { CasesPage } from "@/components/flags/cases-page";

export const metadata: Metadata = { title: "Cases" };

export default function CollegeCases() {
  return (
    <Suspense>
      <CasesPage variant="college" />
    </Suspense>
  );
}
